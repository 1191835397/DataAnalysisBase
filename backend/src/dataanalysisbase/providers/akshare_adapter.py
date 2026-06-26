"""AKShare provider adapter."""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from dataanalysisbase.common.errors import InvalidSecurityId, ProviderError
from dataanalysisbase.domain.contracts import MarketRow
from dataanalysisbase.domain.symbols import SecurityId
from dataanalysisbase.providers.market import MarketSnapshotBatch

MARKET_SPOT_DATASET = "market_spot"


class AkshareAdapter:
    """Fetch and normalize A-share market data from AKShare."""

    name = "akshare"

    def __init__(
        self,
        spot_fetcher: Callable[[], Any] | None = None,
        spot_fetchers: tuple[tuple[str, Callable[[], Any]], ...] | None = None,
        industry_name_fetcher: Callable[[], Any] | None = None,
        industry_cons_fetcher: Callable[[str], Any] | None = None,
        industry_mapping_fetcher: Callable[[], Any] | None = None,
    ) -> None:
        self._spot_fetcher = spot_fetcher
        self._spot_fetchers = spot_fetchers
        self._industry_name_fetcher = industry_name_fetcher
        self._industry_cons_fetcher = industry_cons_fetcher
        self._industry_mapping_fetcher = industry_mapping_fetcher

    def fetch_market_snapshot(self, snapshot_time: datetime) -> MarketSnapshotBatch:
        """Fetch a whole-market spot snapshot and normalize it."""

        try:
            frame = self._fetch_spot_frame()
            records = _records_from_frame(frame)
            industry_by_code = self._fetch_industry_by_code()
            rows = [
                _row_from_record(record, snapshot_time, industry_by_code=industry_by_code)
                for record in records
            ]
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(self.name, MARKET_SPOT_DATASET, str(exc)) from exc

        return MarketSnapshotBatch(
            snapshot_time=snapshot_time,
            source=self.name,
            expected=len(records),
            rows=rows,
        )

    def _fetch_spot_frame(self) -> Any:
        if self._spot_fetcher is not None:
            return self._spot_fetcher()
        if self._spot_fetchers is not None:
            return _fetch_first_available(self._spot_fetchers)

        try:
            ak = importlib.import_module("akshare")
        except ImportError as exc:
            raise ProviderError(
                self.name,
                MARKET_SPOT_DATASET,
                "akshare is not installed; install backend providers extra",
                retryable=False,
            ) from exc
        fetchers = tuple(
            (name, fetcher)
            for name in ("stock_zh_a_spot_em", "stock_zh_a_spot")
            if callable(fetcher := getattr(ak, name, None))
        )
        return _fetch_first_available(fetchers)

    def _fetch_industry_by_code(self) -> dict[str, str]:
        industry_by_code = self._fetch_industry_mapping_by_code()
        name_fetcher, cons_fetcher = self._industry_fetchers()
        if name_fetcher is None or cons_fetcher is None:
            return industry_by_code

        try:
            industry_records = _records_from_frame(name_fetcher())
        except Exception:
            return industry_by_code

        for industry_record in industry_records:
            industry_name = _string_value(
                industry_record,
                "板块名称",
                "行业",
                "industry_name",
                "name",
            )
            if industry_name is None:
                continue
            try:
                cons_records = _records_from_frame(cons_fetcher(industry_name))
            except Exception:
                continue
            for cons_record in cons_records:
                security_id = _security_id_from_record(cons_record)
                if security_id is not None:
                    industry_by_code[security_id] = industry_name
        return industry_by_code

    def _fetch_industry_mapping_by_code(self) -> dict[str, str]:
        if self._industry_mapping_fetcher is None:
            return {}

        try:
            return _industry_mapping_from_source(self._industry_mapping_fetcher())
        except Exception:
            return {}

    def _industry_fetchers(self) -> tuple[Callable[[], Any] | None, Callable[[str], Any] | None]:
        if self._industry_name_fetcher is not None and self._industry_cons_fetcher is not None:
            return self._industry_name_fetcher, self._industry_cons_fetcher
        if self._spot_fetcher is not None or self._spot_fetchers is not None:
            return None, None

        try:
            ak = importlib.import_module("akshare")
        except ImportError:
            return None, None

        name_fetcher = getattr(ak, "stock_board_industry_name_em", None)
        cons_fetcher = getattr(ak, "stock_board_industry_cons_em", None)
        if not callable(name_fetcher) or not callable(cons_fetcher):
            return None, None
        return name_fetcher, cons_fetcher


def _fetch_first_available(fetchers: tuple[tuple[str, Callable[[], Any]], ...]) -> Any:
    if not fetchers:
        raise ProviderError(
            "akshare",
            MARKET_SPOT_DATASET,
            "no AKShare market spot fetchers are available",
            retryable=False,
        )

    errors: list[str] = []
    for name, fetcher in fetchers:
        try:
            return fetcher()
        except Exception as exc:
            errors.append(f"{name}: {_single_line(str(exc))}")
    raise ProviderError(
        "akshare",
        MARKET_SPOT_DATASET,
        f"all AKShare market spot fetchers failed: {'; '.join(errors)}",
    )


def _records_from_frame(frame: Any) -> list[Mapping[str, Any]]:
    if frame is None:
        return []
    if hasattr(frame, "to_dict"):
        raw = frame.to_dict(orient="records")
        if isinstance(raw, list):
            return [record for record in raw if isinstance(record, Mapping)]
    if isinstance(frame, list):
        return [record for record in frame if isinstance(record, Mapping)]
    msg = "AKShare market spot response must be a DataFrame-like object"
    raise TypeError(msg)


def _industry_mapping_from_source(source: Any) -> dict[str, str]:
    if isinstance(source, Mapping):
        return _industry_mapping_from_mapping(source)

    industry_by_code: dict[str, str] = {}
    for record in _records_from_frame(source):
        security_id = _security_id_from_record(record)
        industry = _string_value(
            record,
            "行业",
            "industry",
            "industry_code",
            "industry_name",
            "板块名称",
            "sector",
            "sector_name",
        )
        if security_id is not None and industry is not None:
            industry_by_code[security_id] = industry
    return industry_by_code


def _industry_mapping_from_mapping(source: Mapping[Any, Any]) -> dict[str, str]:
    industry_by_code: dict[str, str] = {}
    for raw_code, raw_industry in source.items():
        industry = str(raw_industry).strip() if raw_industry is not None else ""
        if not industry:
            continue
        try:
            security_id = str(SecurityId.parse(str(raw_code)))
        except InvalidSecurityId:
            continue
        industry_by_code[security_id] = industry
    return industry_by_code


def _row_from_record(
    record: Mapping[str, Any],
    snapshot_time: datetime,
    *,
    industry_by_code: Mapping[str, str],
) -> MarketRow:
    raw_code = _string_value(record, "代码", "code", "symbol")
    raw_name = _string_value(record, "名称", "name")
    if raw_code is None or raw_name is None:
        raise ProviderError(
            "akshare",
            MARKET_SPOT_DATASET,
            "AKShare market spot row missing code or name",
            retryable=False,
        )

    try:
        security_id = str(SecurityId.parse(raw_code))
    except InvalidSecurityId as exc:
        raise ProviderError(
            "akshare",
            MARKET_SPOT_DATASET,
            f"Invalid AKShare security code: {raw_code}",
            retryable=False,
        ) from exc

    return MarketRow(
        snapshot_time=snapshot_time,
        security_id=security_id,
        name=raw_name,
        source="akshare",
        fetched_at=snapshot_time,
        price=_float_value(record, "最新价", "price"),
        change_pct=_float_value(record, "涨跌幅", "change_pct"),
        volume=_float_value(record, "成交量", "volume"),
        amount=_float_value(record, "成交额", "amount"),
        turnover_rate=_float_value(record, "换手率", "turnover_rate"),
        volume_ratio=_float_value(record, "量比", "volume_ratio"),
        pe_ttm=_float_value(record, "市盈率-动态", "pe_ttm"),
        pb=_float_value(record, "市净率", "pb"),
        market_cap=_float_value(record, "总市值", "market_cap"),
        industry_code=_string_value(record, "行业", "industry", "industry_code")
        or industry_by_code.get(security_id),
    )


def _security_id_from_record(record: Mapping[str, Any]) -> str | None:
    raw_code = _string_value(record, "代码", "code", "symbol")
    if raw_code is None:
        return None
    try:
        return str(SecurityId.parse(raw_code))
    except InvalidSecurityId:
        return None


def _string_value(record: Mapping[str, Any], *names: str) -> str | None:
    value = _first_present(record, names)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _float_value(record: Mapping[str, Any], *names: str) -> float | None:
    value = _first_present(record, names)
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip().replace(",", "")
        if not value or value in {"-", "--"}:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_present(record: Mapping[str, Any], names: tuple[str, ...]) -> Any | None:
    for name in names:
        if name in record:
            return record[name]
    return None


def _single_line(message: str) -> str:
    return " ".join(message.split())
