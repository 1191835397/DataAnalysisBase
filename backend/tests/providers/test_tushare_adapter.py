from dataanalysisbase.common.errors import ProviderError
from dataanalysisbase.providers import TushareAdapter


def test_tushare_adapter_maps_stock_basic_industry_records() -> None:
    adapter = TushareAdapter(
        stock_basic_fetcher=lambda **_kwargs: FakeFrame(
            [
                {"ts_code": "600519.SH", "name": "贵州茅台", "industry": "白酒"},
                {"ts_code": "300750.SZ", "name": "宁德时代", "industry": "电池"},
                {"ts_code": "000001.SZ", "name": "平安银行", "industry": ""},
                {"ts_code": "invalid", "name": "坏数据", "industry": "未知"},
            ]
        )
    )

    mapping = adapter.fetch_industry_mapping()

    assert mapping == {"600519.SH": "白酒", "300750.SZ": "电池"}


def test_tushare_adapter_requires_token_without_injected_fetcher() -> None:
    adapter = TushareAdapter(token=None)

    try:
        adapter.fetch_industry_mapping()
    except ProviderError as exc:
        assert exc.provider == "tushare"
        assert exc.dataset_type == "industry_mapping"
        assert exc.retryable is False
        assert "token is not configured" in str(exc)
    else:
        raise AssertionError("expected ProviderError")


class FakeFrame:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self.records = records

    def to_dict(self, *, orient: str) -> list[dict[str, object]]:
        assert orient == "records"
        return self.records
