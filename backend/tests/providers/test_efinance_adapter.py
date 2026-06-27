from dataanalysisbase.common.errors import ProviderError
from dataanalysisbase.providers import EfinanceAdapter


def test_efinance_adapter_maps_realtime_quote_industry_records() -> None:
    adapter = EfinanceAdapter(
        realtime_quotes_fetcher=lambda: FakeFrame(
            [
                {"股票代码": "600519", "股票名称": "贵州茅台", "所属行业": "白酒"},
                {"股票代码": "300750", "股票名称": "宁德时代", "所属行业": "电池"},
                {"股票代码": "000001", "股票名称": "平安银行", "所属行业": ""},
                {"股票代码": "invalid", "股票名称": "坏数据", "所属行业": "未知"},
            ]
        )
    )

    mapping = adapter.fetch_industry_mapping()

    assert mapping == {"600519.SH": "白酒", "300750.SZ": "电池"}


def test_efinance_adapter_reports_missing_dependency_without_injected_fetcher(monkeypatch) -> None:
    def _missing_module(name: str):
        if name == "efinance":
            raise ImportError(name)
        raise AssertionError(f"unexpected import: {name}")

    monkeypatch.setattr(
        "dataanalysisbase.providers.efinance_adapter.importlib.import_module",
        _missing_module,
    )
    adapter = EfinanceAdapter()

    try:
        adapter.fetch_industry_mapping()
    except ProviderError as exc:
        assert exc.provider == "efinance"
        assert exc.dataset_type == "industry_mapping"
        assert exc.retryable is False
        assert "efinance is not installed" in str(exc)
    else:
        raise AssertionError("expected ProviderError")


class FakeFrame:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self.records = records

    def to_dict(self, *, orient: str) -> list[dict[str, object]]:
        assert orient == "records"
        return self.records
