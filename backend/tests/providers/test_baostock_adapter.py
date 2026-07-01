from dataanalysisbase.common.errors import ProviderError
from dataanalysisbase.providers import BaostockAdapter


def test_baostock_adapter_maps_stock_industry_records() -> None:
    module = FakeBaostockModule(
        rows=[
            ["sh.600519", "贵州茅台", "白酒"],
            ["sz.300750", "宁德时代", "电池"],
            ["sz.000001", "平安银行", ""],
            ["bad-code", "坏数据", "未知"],
        ]
    )
    adapter = BaostockAdapter(module=module)

    mapping = adapter.fetch_industry_mapping()

    assert mapping == {"600519.SH": "白酒", "300750.SZ": "电池"}
    assert module.logged_out is True


def test_baostock_adapter_reports_login_failure() -> None:
    adapter = BaostockAdapter(module=FakeBaostockModule(login_error="auth failed"))

    try:
        adapter.fetch_industry_mapping()
    except ProviderError as exc:
        assert exc.provider == "baostock"
        assert exc.dataset_type == "industry_mapping"
        assert exc.retryable is False
        assert "auth failed" in str(exc)
    else:
        raise AssertionError("expected ProviderError")


def test_baostock_adapter_reports_missing_dependency(monkeypatch) -> None:
    def _missing_module(name: str):
        if name == "baostock":
            raise ImportError(name)
        raise AssertionError(f"unexpected import: {name}")

    monkeypatch.setattr(
        "dataanalysisbase.providers.baostock_adapter.importlib.import_module",
        _missing_module,
    )
    adapter = BaostockAdapter()

    try:
        adapter.fetch_industry_mapping()
    except ProviderError as exc:
        assert exc.provider == "baostock"
        assert exc.dataset_type == "industry_mapping"
        assert exc.retryable is False
        assert "baostock is not installed" in str(exc)
    else:
        raise AssertionError("expected ProviderError")


class FakeResult:
    def __init__(
        self,
        *,
        fields: list[str] | None = None,
        rows: list[list[str]] | None = None,
        error_code: str = "0",
        error_msg: str = "",
    ) -> None:
        self.fields = fields or []
        self.rows = rows or []
        self.error_code = error_code
        self.error_msg = error_msg
        self.index = -1

    def next(self) -> bool:
        self.index += 1
        return self.index < len(self.rows)

    def get_row_data(self) -> list[str]:
        return self.rows[self.index]


class FakeBaostockModule:
    def __init__(
        self,
        *,
        rows: list[list[str]] | None = None,
        login_error: str = "",
    ) -> None:
        self.rows = rows or []
        self.login_error = login_error
        self.logged_out = False

    def login(self) -> FakeResult:
        if self.login_error:
            return FakeResult(error_code="1", error_msg=self.login_error)
        return FakeResult()

    def logout(self) -> None:
        self.logged_out = True

    def query_stock_industry(self) -> FakeResult:
        return FakeResult(
            fields=["code", "code_name", "industry"],
            rows=self.rows,
        )
