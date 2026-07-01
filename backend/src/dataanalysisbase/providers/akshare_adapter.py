"""AKShare provider adapter."""

from __future__ import annotations

import importlib
import math
from collections.abc import Callable, Mapping
from datetime import date, datetime
from typing import Any

from dataanalysisbase.common.errors import InvalidSecurityId, ProviderError
from dataanalysisbase.domain.contracts import MarketRow
from dataanalysisbase.domain.symbols import SecurityId
from dataanalysisbase.providers.market import MarketSnapshotBatch

MARKET_SPOT_DATASET = "market_spot"
TRADE_CALENDAR_DATASET = "trade_calendar"


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
        bj_stock_info_fetcher: Callable[[], Any] | None = None,
        listing_date_fetchers: tuple[Callable[[], Any], ...] | None = None,
        ex_dividend_fetcher: Callable[[date], Any] | None = None,
        ex_dividend_history_fetchers: tuple[Callable[[], Any], ...] | None = None,
        trade_calendar_fetcher: Callable[[], Any] | None = None,
    ) -> None:
        self._spot_fetcher = spot_fetcher
        self._spot_fetchers = spot_fetchers
        self._industry_name_fetcher = industry_name_fetcher
        self._industry_cons_fetcher = industry_cons_fetcher
        self._industry_mapping_fetcher = industry_mapping_fetcher
        self._bj_stock_info_fetcher = bj_stock_info_fetcher
        self._listing_date_fetchers = listing_date_fetchers
        self._ex_dividend_fetcher = ex_dividend_fetcher
        self._ex_dividend_history_fetchers = ex_dividend_history_fetchers
        self._trade_calendar_fetcher = trade_calendar_fetcher

    def fetch_market_snapshot(self, snapshot_time: datetime) -> MarketSnapshotBatch:
        """Fetch a whole-market spot snapshot and normalize it."""

        try:
            frame = self._fetch_spot_frame()
            records = _records_from_frame(frame)
            industry_by_code = self._fetch_industry_by_code()
            listing_date_by_code = self._fetch_listing_date_by_code()
            ex_dividend_codes = self._fetch_ex_dividend_codes(snapshot_time.date())
            rows = [
                _row_from_record(
                    record,
                    snapshot_time,
                    industry_by_code=industry_by_code,
                    listing_date_by_code=listing_date_by_code,
                    ex_dividend_codes=ex_dividend_codes,
                )
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

    def fetch_industry_mapping(self) -> dict[str, str]:
        """Fetch security-to-industry mapping from provider-native industry boards."""

        industry_by_code: dict[str, str] = {}
        name_fetcher, cons_fetcher = self._industry_fetchers()
        if name_fetcher is not None and cons_fetcher is not None:
            industry_by_code.update(self._fetch_board_industry_by_code(name_fetcher, cons_fetcher))

        for security_id, industry in self._fetch_bj_industry_by_code().items():
            industry_by_code.setdefault(security_id, industry)
        return industry_by_code

    def fetch_trade_dates(self) -> set[date]:
        """Fetch exchange trading dates from AKShare's Sina trading calendar."""

        fetcher = self._trade_calendar_fetcher
        if fetcher is None:
            try:
                ak = importlib.import_module("akshare")
            except ImportError as exc:
                raise ProviderError(
                    self.name,
                    TRADE_CALENDAR_DATASET,
                    "akshare is not installed; install backend providers extra",
                    retryable=False,
                ) from exc
            fetcher = getattr(ak, "tool_trade_date_hist_sina", None)
        if not callable(fetcher):
            raise ProviderError(
                self.name,
                TRADE_CALENDAR_DATASET,
                "AKShare trade calendar fetcher is not available",
                retryable=False,
            )

        try:
            records = _records_from_frame(fetcher())
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(self.name, TRADE_CALENDAR_DATASET, str(exc)) from exc

        trade_dates: set[date] = set()
        for record in records:
            trade_date = _date_value(
                record,
                "trade_date",
                "交易日",
                "日期",
                "date",
            )
            if trade_date is not None:
                trade_dates.add(trade_date)
        return trade_dates

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
        if industry_by_code:
            return industry_by_code

        name_fetcher, cons_fetcher = self._industry_fetchers()
        if name_fetcher is None or cons_fetcher is None:
            return industry_by_code

        return self._fetch_board_industry_by_code(name_fetcher, cons_fetcher)

    def _fetch_board_industry_by_code(
        self,
        name_fetcher: Callable[[], Any],
        cons_fetcher: Callable[[str], Any],
    ) -> dict[str, str]:
        try:
            industry_records = _records_from_frame(name_fetcher())
        except Exception:
            return {}

        industry_by_code: dict[str, str] = {}
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

    def _fetch_listing_date_by_code(self) -> dict[str, date]:
        listing_date_by_code: dict[str, date] = {}
        for fetcher in self._listing_date_fetchers_or_default():
            try:
                records = _records_from_frame(fetcher())
            except Exception:
                continue
            for record in records:
                security_id = _security_id_from_record(record)
                listing_date = _date_value(
                    record,
                    "上市时间",
                    "上市日期",
                    "A股上市日期",
                    "上市日期/时间",
                    "listing_date",
                    "list_date",
                )
                if security_id is not None and listing_date is not None:
                    listing_date_by_code[security_id] = listing_date
        return listing_date_by_code

    def _listing_date_fetchers_or_default(self) -> tuple[Callable[[], Any], ...]:
        if self._listing_date_fetchers is not None:
            return self._listing_date_fetchers
        if self._spot_fetcher is not None or self._spot_fetchers is not None:
            return ()

        try:
            ak = importlib.import_module("akshare")
        except ImportError:
            return ()

        sh_fetcher = getattr(ak, "stock_info_sh_name_code", None)
        sz_fetcher = getattr(ak, "stock_info_sz_name_code", None)
        bj_fetcher = getattr(ak, "stock_info_bj_name_code", None)
        fetchers: list[Callable[[], Any]] = []
        if callable(sh_fetcher):
            fetchers.extend(
                [
                    lambda: sh_fetcher(symbol="主板A股"),
                    lambda: sh_fetcher(symbol="科创板"),
                ]
            )
        if callable(sz_fetcher):
            fetchers.append(lambda: sz_fetcher(symbol="A股列表"))
        if callable(bj_fetcher):
            fetchers.append(bj_fetcher)
        return tuple(fetchers)

    def _fetch_ex_dividend_codes(self, snapshot_date: date) -> set[str]:
        ex_dividend_codes = self._fetch_ex_dividend_notify_codes(snapshot_date)
        ex_dividend_codes.update(self._fetch_ex_dividend_history_codes(snapshot_date))
        return ex_dividend_codes

    def _fetch_ex_dividend_notify_codes(self, snapshot_date: date) -> set[str]:
        fetcher = self._ex_dividend_fetcher
        if fetcher is None:
            if self._spot_fetcher is not None or self._spot_fetchers is not None:
                return set()
            try:
                ak = importlib.import_module("akshare")
            except ImportError:
                return set()
            provider_fetcher = getattr(ak, "news_trade_notify_dividend_baidu", None)
            if not callable(provider_fetcher):
                return set()

            def fetcher(day: date) -> Any:
                return provider_fetcher(date=day.strftime("%Y%m%d"))

        try:
            records = _records_from_frame(fetcher(snapshot_date))
        except Exception:
            return set()

        ex_dividend_codes: set[str] = set()
        for record in records:
            event_date = _date_value(
                record,
                "除权日",
                "除权除息日",
                "派息日",
                "dividend_date",
                "ex_dividend_date",
            )
            if event_date is not None and event_date != snapshot_date:
                continue
            security_id = _security_id_from_record(record)
            if security_id is not None:
                ex_dividend_codes.add(security_id)
        return ex_dividend_codes

    def _fetch_ex_dividend_history_codes(self, snapshot_date: date) -> set[str]:
        ex_dividend_codes: set[str] = set()
        for fetcher in self._ex_dividend_history_fetchers_or_default(snapshot_date):
            try:
                records = _records_from_frame(fetcher())
            except Exception:
                continue
            for record in records:
                event_date = _date_value(
                    record,
                    "除权除息日",
                    "除权日",
                    "派息日",
                    "ex_dividend_date",
                    "dividend_date",
                )
                if event_date != snapshot_date:
                    continue
                security_id = _security_id_from_record(record)
                if security_id is not None:
                    ex_dividend_codes.add(security_id)
        return ex_dividend_codes

    def _ex_dividend_history_fetchers_or_default(
        self,
        snapshot_date: date,
    ) -> tuple[Callable[[], Any], ...]:
        if self._ex_dividend_history_fetchers is not None:
            return self._ex_dividend_history_fetchers
        if self._spot_fetcher is not None or self._spot_fetchers is not None:
            return ()

        try:
            ak = importlib.import_module("akshare")
        except ImportError:
            return ()
        report_fetcher = getattr(ak, "stock_fhps_em", None)
        if not callable(report_fetcher):
            return ()

        report_periods = _candidate_report_periods(snapshot_date)
        return tuple(
            lambda period=period: report_fetcher(date=period)
            for period in report_periods
        )

    def _fetch_bj_industry_by_code(self) -> dict[str, str]:
        fetcher = self._bj_stock_info_fetcher
        if fetcher is None:
            try:
                ak = importlib.import_module("akshare")
            except ImportError:
                return {}
            fetcher = getattr(ak, "stock_info_bj_name_code", None)
        if not callable(fetcher):
            return {}

        try:
            records = _records_from_frame(fetcher())
        except Exception:
            return {}

        industry_by_code: dict[str, str] = {}
        for record in records:
            security_id = _security_id_from_record(record)
            industry = _string_value(
                record,
                "所属行业",
                "行业",
                "industry",
                "industry_code",
                "industry_name",
            )
            if security_id is not None and industry is not None:
                industry_by_code[security_id] = industry
        return industry_by_code

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
    listing_date_by_code: Mapping[str, date],
    ex_dividend_codes: set[str],
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

    price = _float_value(record, "最新价", "price")
    volume = _float_value(record, "成交量", "volume")
    amount = _float_value(record, "成交额", "amount")
    explicit_ex_dividend = _bool_value(
        record,
        "ex_dividend",
        "除权除息",
        "除权",
        "除息",
        "is_ex_dividend",
    )
    return MarketRow(
        snapshot_time=snapshot_time,
        security_id=security_id,
        name=raw_name,
        source="akshare",
        fetched_at=snapshot_time,
        price=price,
        change_pct=_float_value(record, "涨跌幅", "change_pct"),
        volume=volume,
        amount=amount,
        turnover_rate=_float_value(record, "换手率", "turnover_rate"),
        volume_ratio=_float_value(record, "量比", "volume_ratio"),
        pe_ttm=_float_value(record, "市盈率-动态", "pe_ttm"),
        pb=_float_value(record, "市净率", "pb"),
        market_cap=_float_value(record, "总市值", "market_cap"),
        industry_code=_string_value(record, "行业", "industry", "industry_code")
        or industry_by_code.get(security_id),
        listing_date=_date_value(
            record,
            "上市时间",
            "上市日期",
            "A股上市日期",
            "上市日期/时间",
            "listing_date",
            "list_date",
        )
        or listing_date_by_code.get(security_id),
        ex_dividend=(
            explicit_ex_dividend
            if explicit_ex_dividend is not None
            else security_id in ex_dividend_codes
        ),
        is_suspended=_is_suspended(record, price=price, volume=volume, amount=amount),
    )


def _security_id_from_record(record: Mapping[str, Any]) -> str | None:
    raw_code = _string_value(
        record,
        "security_id",
        "股票代码",
        "证券代码",
        "A股代码",
        "代码",
        "code",
        "symbol",
    )
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
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _date_value(record: Mapping[str, Any], *names: str) -> date | None:
    value = _first_present(record, names)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text or text in {"-", "--"}:
        return None
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _candidate_report_periods(snapshot_date: date) -> tuple[str, ...]:
    periods: list[str] = []
    for year in range(snapshot_date.year, snapshot_date.year - 3, -1):
        for month, day in ((12, 31), (9, 30), (6, 30), (3, 31)):
            period = date(year, month, day)
            if period <= snapshot_date:
                periods.append(period.strftime("%Y%m%d"))
    return tuple(periods[:8])


def _is_suspended(
    record: Mapping[str, Any],
    *,
    price: float | None,
    volume: float | None,
    amount: float | None,
) -> bool:
    explicit = _bool_value(
        record,
        "is_suspended",
        "suspended",
        "停牌",
        "是否停牌",
        "交易状态",
        "状态",
        "trade_status",
        "status",
    )
    if explicit is not None:
        return explicit
    if price is None:
        return True
    return volume == 0 and amount == 0


def _bool_value(record: Mapping[str, Any], *names: str) -> bool | None:
    value = _first_present(record, names)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return bool(value)
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"true", "1", "yes", "y", "停牌", "暂停交易", "suspended"}:
        return True
    if text in {"false", "0", "no", "n", "交易", "正常", "active", "trading"}:
        return False
    return "停牌" in text or "suspend" in text


def _first_present(record: Mapping[str, Any], names: tuple[str, ...]) -> Any | None:
    for name in names:
        if name in record:
            return record[name]
    return None


def _single_line(message: str) -> str:
    return " ".join(message.split())
