from __future__ import annotations

import math
from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from dataanalysisbase.common.errors import ProviderError
from dataanalysisbase.providers import AkshareAdapter


def test_akshare_adapter_maps_market_spot_rows() -> None:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    adapter = AkshareAdapter(
        spot_fetcher=lambda: FakeFrame(
            [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "最新价": "1688.00",
                    "涨跌幅": "1.25",
                    "成交量": "123456",
                    "成交额": "208000000",
                    "换手率": "0.31",
                    "量比": "1.2",
                    "市盈率-动态": "24.5",
                    "市净率": "8.1",
                    "总市值": "2120000000000",
                    "行业": "白酒",
                    "上市时间": "20010827",
                },
                {
                    "代码": "300750",
                    "名称": "宁德时代",
                    "最新价": "--",
                    "涨跌幅": "-0.5",
                    "成交量": "100",
                    "成交额": "1000",
                    "换手率": "-",
                    "量比": "0.8",
                    "市盈率-动态": "18.0",
                    "市净率": "3.2",
                    "总市值": "900000000000",
                    "行业": "电池",
                },
            ]
        )
    )

    batch = adapter.fetch_market_snapshot(snapshot_time)

    assert batch.source == "akshare"
    assert batch.expected == 2
    assert len(batch.rows) == 2

    first = batch.rows[0]
    assert first.security_id == "600519.SH"
    assert first.name == "贵州茅台"
    assert first.price == 1688.0
    assert first.change_pct == 1.25
    assert first.volume == 123456.0
    assert first.amount == 208000000.0
    assert first.turnover_rate == 0.31
    assert first.volume_ratio == 1.2
    assert first.pe_ttm == 24.5
    assert first.pb == 8.1
    assert first.market_cap == 2120000000000.0
    assert first.industry_code == "白酒"
    assert first.listing_date == date(2001, 8, 27)
    assert first.fetched_at == snapshot_time

    second = batch.rows[1]
    assert second.security_id == "300750.SZ"
    assert second.price is None
    assert second.turnover_rate is None
    assert second.is_suspended is True


def test_akshare_adapter_maps_explicit_suspended_status() -> None:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    adapter = AkshareAdapter(
        spot_fetcher=lambda: FakeFrame(
            [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "最新价": "1688.00",
                    "成交量": "123456",
                    "成交额": "208000000",
                    "交易状态": "正常",
                },
                {
                    "代码": "000001",
                    "名称": "平安银行",
                    "最新价": "10.00",
                    "成交量": "100",
                    "成交额": "1000",
                    "交易状态": "停牌",
                },
            ]
        )
    )

    batch = adapter.fetch_market_snapshot(snapshot_time)

    assert batch.rows[0].is_suspended is False
    assert batch.rows[1].is_suspended is True


def test_akshare_adapter_marks_suspended_from_suspend_notify_source() -> None:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    seen_dates: list[date] = []
    adapter = AkshareAdapter(
        spot_fetcher=lambda: FakeFrame(
            [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "最新价": "1688.00",
                    "成交量": "123456",
                    "成交额": "208000000",
                },
                {
                    "代码": "000001",
                    "名称": "平安银行",
                    "最新价": "10.00",
                    "成交量": "100",
                    "成交额": "1000",
                },
            ]
        ),
        suspended_fetcher=lambda day: seen_dates.append(day)
        or FakeFrame(
            [
                {"股票代码": "000001", "停牌日期": "2026-06-23"},
                {"股票代码": "600519", "停牌日期": "2026-06-22"},
            ]
        ),
    )

    batch = adapter.fetch_market_snapshot(snapshot_time)

    assert seen_dates == [date(2026, 6, 23)]
    assert batch.rows[0].is_suspended is False
    assert batch.rows[1].is_suspended is True


def test_akshare_adapter_prefers_explicit_suspended_field_over_suspend_list() -> None:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    adapter = AkshareAdapter(
        spot_fetcher=lambda: FakeFrame(
            [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "最新价": "1688.00",
                    "成交量": "123456",
                    "成交额": "208000000",
                    "is_suspended": False,
                }
            ]
        ),
        suspended_fetcher=lambda _day: FakeFrame(
            [{"股票代码": "600519", "停牌日期": "2026-06-23"}]
        ),
    )

    batch = adapter.fetch_market_snapshot(snapshot_time)

    assert batch.rows[0].is_suspended is False


def test_akshare_adapter_keeps_snapshot_when_suspended_fetch_fails() -> None:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    adapter = AkshareAdapter(
        spot_fetcher=lambda: FakeFrame(
            [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "最新价": "1688.00",
                    "成交量": "123456",
                    "成交额": "208000000",
                }
            ]
        ),
        suspended_fetcher=lambda _day: _raise_fetch_error(),
    )

    batch = adapter.fetch_market_snapshot(snapshot_time)

    assert batch.rows[0].security_id == "600519.SH"
    assert batch.rows[0].is_suspended is False


def test_akshare_adapter_enriches_listing_date_from_stock_lists() -> None:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    adapter = AkshareAdapter(
        spot_fetcher=lambda: FakeFrame(
            [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "最新价": "1688.00",
                    "成交量": "123456",
                    "成交额": "208000000",
                },
                {
                    "代码": "300750",
                    "名称": "宁德时代",
                    "最新价": "200.00",
                    "成交量": "100",
                    "成交额": "1000",
                },
            ]
        ),
        listing_date_fetchers=(
            lambda: FakeFrame(
                [
                    {"证券代码": "600519", "上市日期": "2001-08-27"},
                    {"A股代码": "300750", "A股上市日期": "2018/06/11"},
                ]
            ),
        ),
    )

    batch = adapter.fetch_market_snapshot(snapshot_time)

    assert batch.rows[0].listing_date == date(2001, 8, 27)
    assert batch.rows[1].listing_date == date(2018, 6, 11)


def test_akshare_adapter_prefers_spot_listing_date_over_stock_list() -> None:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    adapter = AkshareAdapter(
        spot_fetcher=lambda: FakeFrame(
            [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "最新价": "1688.00",
                    "成交量": "123456",
                    "成交额": "208000000",
                    "上市日期": "20010827",
                }
            ]
        ),
        listing_date_fetchers=(
            lambda: FakeFrame([{"证券代码": "600519", "上市日期": "1999-01-01"}]),
        ),
    )

    batch = adapter.fetch_market_snapshot(snapshot_time)

    assert batch.rows[0].listing_date == date(2001, 8, 27)


def test_akshare_adapter_keeps_snapshot_when_listing_date_fetch_fails() -> None:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    adapter = AkshareAdapter(
        spot_fetcher=lambda: FakeFrame(
            [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "最新价": "1688.00",
                    "成交量": "123456",
                    "成交额": "208000000",
                }
            ]
        ),
        listing_date_fetchers=(_raise_fetch_error,),
    )

    batch = adapter.fetch_market_snapshot(snapshot_time)

    assert batch.rows[0].security_id == "600519.SH"
    assert batch.rows[0].listing_date is None


def test_akshare_adapter_marks_ex_dividend_from_trade_calendar() -> None:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    seen_dates: list[date] = []
    adapter = AkshareAdapter(
        spot_fetcher=lambda: FakeFrame(
            [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "最新价": "1688.00",
                    "成交量": "123456",
                    "成交额": "208000000",
                },
                {
                    "代码": "300750",
                    "名称": "宁德时代",
                    "最新价": "200.00",
                    "成交量": "100",
                    "成交额": "1000",
                },
            ]
        ),
        ex_dividend_fetcher=lambda day: seen_dates.append(day)
        or FakeFrame(
            [
                {"股票代码": "600519", "除权日": "2026-06-23"},
                {"股票代码": "300750", "除权日": "2026-06-22"},
            ]
        ),
    )

    batch = adapter.fetch_market_snapshot(snapshot_time)

    assert seen_dates == [date(2026, 6, 23)]
    assert batch.rows[0].ex_dividend is True
    assert batch.rows[1].ex_dividend is False


def test_akshare_adapter_fetches_trade_calendar_dates() -> None:
    adapter = AkshareAdapter(
        trade_calendar_fetcher=lambda: FakeFrame(
            [
                {"trade_date": date(2026, 1, 2)},
                {"trade_date": "2026-01-05"},
                {"trade_date": "bad-date"},
            ]
        )
    )

    trade_dates = adapter.fetch_trade_dates()

    assert trade_dates == {date(2026, 1, 2), date(2026, 1, 5)}


def test_akshare_adapter_prefers_explicit_ex_dividend_field() -> None:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    adapter = AkshareAdapter(
        spot_fetcher=lambda: FakeFrame(
            [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "最新价": "1688.00",
                    "成交量": "123456",
                    "成交额": "208000000",
                    "ex_dividend": True,
                },
                {
                    "代码": "300750",
                    "名称": "宁德时代",
                    "最新价": "200.00",
                    "成交量": "100",
                    "成交额": "1000",
                    "ex_dividend": False,
                },
            ]
        ),
        ex_dividend_fetcher=lambda _day: FakeFrame(
            [{"股票代码": "300750", "除权日": "2026-06-23"}]
        ),
    )

    batch = adapter.fetch_market_snapshot(snapshot_time)

    assert batch.rows[0].ex_dividend is True
    assert batch.rows[1].ex_dividend is False


def test_akshare_adapter_marks_ex_dividend_from_history_reports() -> None:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    adapter = AkshareAdapter(
        spot_fetcher=lambda: FakeFrame(
            [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "最新价": "1688.00",
                    "成交量": "123456",
                    "成交额": "208000000",
                },
                {
                    "代码": "300750",
                    "名称": "宁德时代",
                    "最新价": "200.00",
                    "成交量": "100",
                    "成交额": "1000",
                },
            ]
        ),
        ex_dividend_history_fetchers=(
            lambda: FakeFrame(
                [
                    {"代码": "600519", "除权除息日": "2026-06-23"},
                    {"代码": "300750", "除权除息日": "2026-06-22"},
                ]
            ),
        ),
    )

    batch = adapter.fetch_market_snapshot(snapshot_time)

    assert batch.rows[0].ex_dividend is True
    assert batch.rows[1].ex_dividend is False


def test_akshare_adapter_merges_notify_and_history_ex_dividend_sources() -> None:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    adapter = AkshareAdapter(
        spot_fetcher=lambda: FakeFrame(
            [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "最新价": "1688.00",
                    "成交量": "123456",
                    "成交额": "208000000",
                },
                {
                    "代码": "300750",
                    "名称": "宁德时代",
                    "最新价": "200.00",
                    "成交量": "100",
                    "成交额": "1000",
                },
            ]
        ),
        ex_dividend_fetcher=lambda _day: FakeFrame(
            [{"股票代码": "600519", "除权日": "2026-06-23"}]
        ),
        ex_dividend_history_fetchers=(
            lambda: FakeFrame([{"代码": "300750", "除权除息日": "2026-06-23"}]),
        ),
    )

    batch = adapter.fetch_market_snapshot(snapshot_time)

    assert batch.rows[0].ex_dividend is True
    assert batch.rows[1].ex_dividend is True


def test_akshare_adapter_keeps_snapshot_when_ex_dividend_fetch_fails() -> None:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    adapter = AkshareAdapter(
        spot_fetcher=lambda: FakeFrame(
            [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "最新价": "1688.00",
                    "成交量": "123456",
                    "成交额": "208000000",
                }
            ]
        ),
        ex_dividend_fetcher=lambda _day: _raise_fetch_error(),
    )

    batch = adapter.fetch_market_snapshot(snapshot_time)

    assert batch.rows[0].security_id == "600519.SH"
    assert batch.rows[0].ex_dividend is False


def test_akshare_adapter_keeps_snapshot_when_ex_dividend_history_fetch_fails() -> None:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    adapter = AkshareAdapter(
        spot_fetcher=lambda: FakeFrame(
            [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "最新价": "1688.00",
                    "成交量": "123456",
                    "成交额": "208000000",
                }
            ]
        ),
        ex_dividend_history_fetchers=(_raise_fetch_error,),
    )

    batch = adapter.fetch_market_snapshot(snapshot_time)

    assert batch.rows[0].security_id == "600519.SH"
    assert batch.rows[0].ex_dividend is False


def test_akshare_adapter_normalizes_non_finite_numbers() -> None:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    adapter = AkshareAdapter(
        spot_fetcher=lambda: FakeFrame(
            [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "最新价": math.nan,
                    "涨跌幅": "nan",
                    "成交额": "inf",
                    "量比": "-inf",
                }
            ]
        )
    )

    batch = adapter.fetch_market_snapshot(snapshot_time)

    row = batch.rows[0]
    assert row.price is None
    assert row.change_pct is None
    assert row.amount is None
    assert row.volume_ratio is None


def test_akshare_adapter_rejects_rows_missing_code_or_name() -> None:
    adapter = AkshareAdapter(spot_fetcher=lambda: FakeFrame([{"代码": "600519"}]))
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    with pytest.raises(ProviderError) as exc_info:
        adapter.fetch_market_snapshot(snapshot_time)

    assert exc_info.value.provider == "akshare"
    assert exc_info.value.dataset_type == "market_spot"
    assert exc_info.value.retryable is False


def test_akshare_adapter_wraps_fetch_errors() -> None:
    adapter = AkshareAdapter(spot_fetcher=_raise_fetch_error)
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    with pytest.raises(ProviderError) as exc_info:
        adapter.fetch_market_snapshot(snapshot_time)

    assert exc_info.value.provider == "akshare"
    assert exc_info.value.dataset_type == "market_spot"
    assert "upstream unavailable" in str(exc_info.value)


def test_akshare_adapter_falls_back_to_secondary_spot_fetcher() -> None:
    calls: list[str] = []
    adapter = AkshareAdapter(
        spot_fetchers=(
            ("stock_zh_a_spot_em", _tracked_failure("primary disconnected", calls, "primary")),
            (
                "stock_zh_a_spot",
                lambda: FakeFrame(
                    [
                        {
                            "code": "600519",
                            "name": "贵州茅台",
                            "price": "1688.00",
                            "change_pct": "1.25",
                        }
                    ]
                ),
            ),
        )
    )
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    batch = adapter.fetch_market_snapshot(snapshot_time)

    assert calls == ["primary"]
    assert batch.expected == 1
    assert batch.rows[0].security_id == "600519.SH"
    assert batch.rows[0].price == 1688.0


def test_akshare_adapter_enriches_missing_industry_from_board_cons() -> None:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    adapter = AkshareAdapter(
        spot_fetcher=lambda: FakeFrame(
            [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "最新价": "1688.00",
                }
            ]
        ),
        industry_name_fetcher=lambda: FakeFrame([{"板块名称": "白酒"}]),
        industry_cons_fetcher=lambda symbol: FakeFrame(
            [{"代码": "600519", "名称": "贵州茅台"}] if symbol == "白酒" else []
        ),
    )

    batch = adapter.fetch_market_snapshot(snapshot_time)

    assert batch.rows[0].industry_code == "白酒"


def test_akshare_adapter_uses_industry_mapping_fallback() -> None:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    adapter = AkshareAdapter(
        spot_fetcher=lambda: FakeFrame(
            [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "最新价": "1688.00",
                }
            ]
        ),
        industry_mapping_fetcher=lambda: {"600519.SH": "白酒"},
    )

    batch = adapter.fetch_market_snapshot(snapshot_time)

    assert batch.rows[0].industry_code == "白酒"


def test_akshare_adapter_prefers_local_mapping_over_board_industry() -> None:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    adapter = AkshareAdapter(
        spot_fetcher=lambda: FakeFrame(
            [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "最新价": "1688.00",
                }
            ]
        ),
        industry_name_fetcher=lambda: FakeFrame([{"板块名称": "白酒"}]),
        industry_cons_fetcher=lambda symbol: FakeFrame(
            [{"代码": "600519", "名称": "贵州茅台"}] if symbol == "白酒" else []
        ),
        industry_mapping_fetcher=lambda: {"600519.SH": "备用行业"},
    )

    batch = adapter.fetch_market_snapshot(snapshot_time)

    assert batch.rows[0].industry_code == "备用行业"


def test_akshare_adapter_skips_board_fetch_when_local_mapping_exists() -> None:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    board_calls: list[str] = []
    adapter = AkshareAdapter(
        spot_fetcher=lambda: FakeFrame(
            [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "最新价": "1688.00",
                }
            ]
        ),
        industry_name_fetcher=lambda: board_calls.append("names")
        or FakeFrame([{"板块名称": "白酒"}]),
        industry_cons_fetcher=lambda symbol: board_calls.append(symbol) or FakeFrame(
            [{"代码": "600519", "名称": "贵州茅台"}]
        ),
        industry_mapping_fetcher=lambda: {"600519.SH": "备用行业"},
    )

    batch = adapter.fetch_market_snapshot(snapshot_time)

    assert batch.rows[0].industry_code == "备用行业"
    assert board_calls == []


def test_akshare_adapter_falls_back_to_board_fetch_when_local_mapping_is_empty() -> None:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    adapter = AkshareAdapter(
        spot_fetcher=lambda: FakeFrame(
            [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "最新价": "1688.00",
                }
            ]
        ),
        industry_name_fetcher=lambda: FakeFrame([{"板块名称": "白酒"}]),
        industry_cons_fetcher=lambda symbol: FakeFrame(
            [{"代码": "600519", "名称": "贵州茅台"}] if symbol == "白酒" else []
        ),
        industry_mapping_fetcher=lambda: {},
    )

    batch = adapter.fetch_market_snapshot(snapshot_time)

    assert batch.rows[0].industry_code == "白酒"


def test_akshare_adapter_fetches_bj_industry_mapping() -> None:
    adapter = AkshareAdapter(
        industry_name_fetcher=lambda: FakeFrame([]),
        industry_cons_fetcher=lambda _symbol: FakeFrame([]),
        bj_stock_info_fetcher=lambda: FakeFrame(
            [
                {"证券代码": "920000", "证券简称": "安徽凤凰", "所属行业": "汽车制造业"},
                {"证券代码": "920001", "证券简称": "纬达光电", "所属行业": "计算机"},
                {"证券代码": "bad-code", "证券简称": "坏数据", "所属行业": "未知"},
                {"证券代码": "920002", "证券简称": "空行业", "所属行业": ""},
            ]
        )
    )

    mapping = adapter.fetch_industry_mapping()

    assert mapping == {"920000.BJ": "汽车制造业", "920001.BJ": "计算机"}


def test_akshare_adapter_keeps_board_industry_before_bj_list() -> None:
    adapter = AkshareAdapter(
        industry_name_fetcher=lambda: FakeFrame([{"板块名称": "板块行业"}]),
        industry_cons_fetcher=lambda _symbol: FakeFrame([{"代码": "920000"}]),
        bj_stock_info_fetcher=lambda: FakeFrame([{"证券代码": "920000", "所属行业": "北交所行业"}]),
    )

    mapping = adapter.fetch_industry_mapping()

    assert mapping == {"920000.BJ": "板块行业"}


def test_akshare_adapter_keeps_snapshot_when_industry_fetch_fails() -> None:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    adapter = AkshareAdapter(
        spot_fetcher=lambda: FakeFrame(
            [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "最新价": "1688.00",
                }
            ]
        ),
        industry_name_fetcher=_raise_fetch_error,
        industry_cons_fetcher=lambda _symbol: FakeFrame([]),
    )

    batch = adapter.fetch_market_snapshot(snapshot_time)

    assert batch.rows[0].security_id == "600519.SH"
    assert batch.rows[0].industry_code is None


def test_akshare_adapter_keeps_snapshot_when_industry_mapping_fails() -> None:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    adapter = AkshareAdapter(
        spot_fetcher=lambda: FakeFrame(
            [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "最新价": "1688.00",
                }
            ]
        ),
        industry_mapping_fetcher=_raise_fetch_error,
    )

    batch = adapter.fetch_market_snapshot(snapshot_time)

    assert batch.rows[0].security_id == "600519.SH"
    assert batch.rows[0].industry_code is None


def test_akshare_adapter_reports_all_spot_fetcher_failures() -> None:
    adapter = AkshareAdapter(
        spot_fetchers=(
            ("stock_zh_a_spot_em", _raise_named_fetch_error("remote disconnected")),
            ("stock_zh_a_spot", _raise_named_fetch_error("timeout")),
        )
    )
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    with pytest.raises(ProviderError) as exc_info:
        adapter.fetch_market_snapshot(snapshot_time)

    message = str(exc_info.value)
    assert "stock_zh_a_spot_em: remote disconnected" in message
    assert "stock_zh_a_spot: timeout" in message


def test_akshare_adapter_errors_when_no_spot_fetcher_is_available() -> None:
    adapter = AkshareAdapter(spot_fetchers=())
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    with pytest.raises(ProviderError) as exc_info:
        adapter.fetch_market_snapshot(snapshot_time)

    assert "no AKShare market spot fetchers are available" in str(exc_info.value)
    assert exc_info.value.retryable is False


class FakeFrame:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self.records = records

    def to_dict(self, *, orient: str) -> list[dict[str, object]]:
        assert orient == "records"
        return self.records


def _raise_fetch_error() -> object:
    raise RuntimeError("upstream unavailable")


def _tracked_failure(message: str, calls: list[str], label: str) -> Callable[[], object]:
    def _raise() -> object:
        calls.append(label)
        raise RuntimeError(message)

    return _raise


def _raise_named_fetch_error(message: str) -> Callable[[], object]:
    def _raise() -> object:
        raise RuntimeError(message)

    return _raise
