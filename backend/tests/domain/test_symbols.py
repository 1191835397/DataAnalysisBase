import pytest

from dataanalysisbase.common.errors import InvalidSecurityId, NameNotResolvable, UnsupportedMarket
from dataanalysisbase.domain.enums import Market
from dataanalysisbase.domain.symbols import SecurityId, to_source_code


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("600519", "600519.SH"),
        ("000001", "000001.SZ"),
        ("300750", "300750.SZ"),
        ("920799", "920799.BJ"),
        ("sh600519", "600519.SH"),
        ("600519.SH", "600519.SH"),
        ("00700.HK", "00700.HK"),
        ("AAPL.US", "AAPL.US"),
    ],
)
def test_security_id_parse_common_formats(raw: str, expected: str) -> None:
    assert str(SecurityId.parse(raw)) == expected


def test_security_id_parse_rejects_name() -> None:
    with pytest.raises(NameNotResolvable):
        SecurityId.parse("贵州茅台")


def test_security_id_parse_rejects_unknown_market() -> None:
    with pytest.raises(UnsupportedMarket):
        SecurityId.parse("600519.XX")


def test_security_id_parse_rejects_unknown_numeric_prefix() -> None:
    with pytest.raises(InvalidSecurityId):
        SecurityId.parse("500000")


def test_to_source_code_formats_provider_codes() -> None:
    sid = SecurityId(symbol="600519", market=Market.SH)

    assert to_source_code(sid, "akshare") == "600519"
    assert to_source_code(sid, "tushare") == "600519.SH"
    assert to_source_code(sid, "sina") == "sh600519"
