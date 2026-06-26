from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
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
    assert first.fetched_at == snapshot_time

    second = batch.rows[1]
    assert second.security_id == "300750.SZ"
    assert second.price is None
    assert second.turnover_rate is None


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
