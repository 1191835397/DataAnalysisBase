from pathlib import Path

import pytest

from dataanalysisbase.providers.industry_mapping import (
    load_industry_mapping_file,
    normalize_security_id,
    write_missing_industry_mapping_csv,
)


def test_load_industry_mapping_csv(tmp_path: Path) -> None:
    path = tmp_path / "industry_mapping.csv"
    path.write_text("security_id,industry\n600519.SH,白酒\n300750.SZ,电池\n", encoding="utf-8")

    records = load_industry_mapping_file(path)

    assert records == [
        {"security_id": "600519.SH", "industry": "白酒"},
        {"security_id": "300750.SZ", "industry": "电池"},
    ]


def test_load_industry_mapping_json_object(tmp_path: Path) -> None:
    path = tmp_path / "industry_mapping.json"
    path.write_text('{"600519.SH": "白酒", "300750.SZ": "电池"}', encoding="utf-8")

    records = load_industry_mapping_file(path)

    assert records == [
        {"security_id": "600519.SH", "industry": "白酒"},
        {"security_id": "300750.SZ", "industry": "电池"},
    ]


def test_load_industry_mapping_rejects_unknown_file_type(tmp_path: Path) -> None:
    path = tmp_path / "industry_mapping.txt"
    path.write_text("600519.SH,白酒\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported industry mapping file type"):
        load_industry_mapping_file(path)


def test_normalize_security_id_accepts_common_a_share_formats() -> None:
    assert normalize_security_id("600519") == "600519.SH"
    assert normalize_security_id("sz300750") == "300750.SZ"
    assert normalize_security_id("000001.SZ") == "000001.SZ"
    assert normalize_security_id("not-a-code") is None


def test_write_missing_industry_mapping_csv(tmp_path: Path) -> None:
    path = tmp_path / "missing.csv"

    count = write_missing_industry_mapping_csv(
        path,
        [
            {"security_id": "300750.SZ", "name": "宁德时代", "industry": ""},
            {"security_id": "600519.SH", "name": "贵州茅台", "industry": ""},
        ],
    )

    assert count == 2
    assert path.read_text(encoding="utf-8") == (
        "security_id,name,industry\n"
        "300750.SZ,宁德时代,\n"
        "600519.SH,贵州茅台,\n"
    )
