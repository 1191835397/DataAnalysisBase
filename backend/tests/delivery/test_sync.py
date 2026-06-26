from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dataanalysisbase.config_loader.settings import Settings
from dataanalysisbase.delivery.cli import main
from dataanalysisbase.delivery.sync import run_industry_mapping_sync, run_market_sync
from dataanalysisbase.domain.contracts import MarketRow
from dataanalysisbase.domain.enums import RunStatus
from dataanalysisbase.providers import MarketSnapshotBatch
from dataanalysisbase.storage import DuckDBStore

ROOT_CONFIG = Path(__file__).resolve().parents[3] / "config"


def test_run_market_sync_with_injected_provider_writes_snapshot(tmp_path: Path) -> None:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    duckdb_path = tmp_path / "sync.duckdb"

    result = run_market_sync(
        snapshot_time,
        config_dir=ROOT_CONFIG,
        duckdb_path=duckdb_path,
        provider=MockProvider([_row(snapshot_time, "600519.SH")]),
    )

    assert result.status == RunStatus.SUCCESS
    assert result.actual == 1

    store = DuckDBStore(duckdb_path)
    try:
        rows = store.query("SELECT security_id FROM market_snapshots")
    finally:
        store.close()
    assert rows == [{"security_id": "600519.SH"}]


def test_sync_market_defaults_to_dry_run_json(capsys) -> None:
    exit_code = main(["sync", "market", "--config-dir", str(ROOT_CONFIG), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["command"] == "sync-market"
    assert payload["dry_run"] is True
    assert payload["will_call_provider"] is False
    assert payload["will_write_database"] is False


def test_sync_industry_mapping_defaults_to_dry_run_json(capsys) -> None:
    exit_code = main(["sync", "industry-mapping", "--config-dir", str(ROOT_CONFIG), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["command"] == "sync-industry-mapping"
    assert payload["dry_run"] is True
    assert payload["will_call_provider"] is False
    assert payload["will_write_file"] is False


def test_run_industry_mapping_sync_writes_mapping_file(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(
        "dataanalysisbase.delivery.sync.load_settings",
        lambda: Settings(config_dir=ROOT_CONFIG, data_dir=data_dir),
    )

    result = run_industry_mapping_sync(
        config_dir=ROOT_CONFIG,
        provider=MockIndustryMappingProvider({"600519.SH": "白酒", "300750.SZ": "电池"}),
    )

    assert result.status == "success"
    assert result.records == 2
    assert (data_dir / "industry_mapping.csv").read_text(encoding="utf-8") == (
        "security_id,industry\n300750.SZ,电池\n600519.SH,白酒\n"
    )


class MockProvider:
    name = "mock"

    def __init__(self, rows: list[MarketRow]) -> None:
        self.rows = rows

    def fetch_market_snapshot(self, snapshot_time: datetime) -> MarketSnapshotBatch:
        return MarketSnapshotBatch(
            snapshot_time=snapshot_time,
            source=self.name,
            expected=len(self.rows),
            rows=self.rows,
        )


class MockIndustryMappingProvider:
    name = "mock"

    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = mapping

    def fetch_industry_mapping(self) -> dict[str, str]:
        return self.mapping


def _row(snapshot_time: datetime, security_id: str) -> MarketRow:
    return MarketRow(
        snapshot_time=snapshot_time,
        security_id=security_id,
        name=security_id,
        source="mock",
        fetched_at=snapshot_time,
        price=100,
        change_pct=1.0,
        volume=1000,
        amount=100000,
        volume_ratio=1.2,
        pe_ttm=20,
        pb=3,
        market_cap=1000000,
        industry_code="TEST",
    )
