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

    def __init__(self, spot_fetcher: Callable[[], Any] | None = None) -> None:
        self._spot_fetcher = spot_fetcher

    def fetch_market_snapshot(self, snapshot_time: datetime) -> MarketSnapshotBatch:
        """Fetch a whole-market spot snapshot and normalize it."""

        try:
            frame = self._fetch_spot_frame()
            records = _records_from_frame(frame)
            rows = [_row_from_record(record, snapshot_time) for record in records]
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

        try:
            ak = importlib.import_module("akshare")
        except ImportError as exc:
            raise ProviderError(
                self.name,
                MARKET_SPOT_DATASET,
                "akshare is not installed; install backend providers extra",
                retryable=False,
            ) from exc
        return ak.stock_zh_a_spot_em()


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


def _row_from_record(record: Mapping[str, Any], snapshot_time: datetime) -> MarketRow:
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
        industry_code=_string_value(record, "行业", "industry", "industry_code"),
    )


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
