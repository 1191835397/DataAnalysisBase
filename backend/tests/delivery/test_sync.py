from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from dataanalysisbase.config_loader.settings import Settings
from dataanalysisbase.delivery.cli import main
from dataanalysisbase.delivery.sync import (
    inspect_industry_mapping_coverage,
    run_industry_mapping_backfill,
    run_industry_mapping_sync,
    run_market_sync,
    run_trade_calendar_sync,
)
from dataanalysisbase.domain.contracts import MarketRow
from dataanalysisbase.domain.enums import RunStatus
from dataanalysisbase.providers import MarketSnapshotBatch
from dataanalysisbase.storage import AggregateRepo, DuckDBStore, SnapshotRepo

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
    assert [entry.stage for entry in result.logs] == [
        "provider_fetch",
        "provider_fetch",
        "snapshot_run",
        "snapshot_write",
        "snapshot_run",
        "aggregate_refresh",
        "sync_result",
    ]
    assert result.logs[-1].details["actual"] == 1

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


def test_sync_industry_backfill_defaults_to_dry_run_json(capsys) -> None:
    exit_code = main(["sync", "industry-backfill", "--config-dir", str(ROOT_CONFIG), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["command"] == "industry-backfill"
    assert payload["dry_run"] is True
    assert payload["will_write_database"] is False


def test_sync_trade_calendar_defaults_to_dry_run_json(capsys) -> None:
    exit_code = main(["sync", "trade-calendar", "--config-dir", str(ROOT_CONFIG), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["command"] == "sync-trade-calendar"
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


def test_run_industry_mapping_sync_fails_on_empty_mapping(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(
        "dataanalysisbase.delivery.sync.load_settings",
        lambda: Settings(config_dir=ROOT_CONFIG, data_dir=data_dir),
    )

    result = run_industry_mapping_sync(
        config_dir=ROOT_CONFIG,
        provider=MockIndustryMappingProvider({}),
    )

    assert result.status == "failed"
    assert result.records == 0
    assert result.errors == ["mock: provider returned 0 industry mapping records"]
    assert not (data_dir / "industry_mapping.csv").exists()


def test_run_trade_calendar_sync_updates_schedule_overrides(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir()
    (config_dir / "sync_schedule.yaml").write_text(
        """
version: "1.0"
timezone: "Asia/Shanghai"
holidays:
  - "2025-12-31"
  - "2026-01-01"
  - "2026-02-02"
makeup_trading_days:
  - "2025-12-28"
  - "2026-01-03"
  - "2026-02-01"
jobs:
  market_bulk_snapshot:
    interval_minutes: 30
    trading_sessions:
      - start: "09:30"
        end: "11:30"
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "dataanalysisbase.delivery.sync.load_settings",
        lambda: Settings(config_dir=config_dir, data_dir=data_dir),
    )
    trade_dates = {
        date(2026, 1, 1),
        date(2026, 1, 4),
        date(2026, 1, 5),
    }

    result = run_trade_calendar_sync(
        config_dir=config_dir,
        provider=MockTradeCalendarProvider(trade_dates),
        year=2026,
        through_date=date(2026, 1, 5),
    )

    assert result.status == "success"
    assert result.coverage_start == date(2026, 1, 1)
    assert result.coverage_end == date(2026, 1, 5)
    assert result.trade_dates == 3
    assert result.added_holidays == 1
    assert result.added_makeup_trading_days == 1
    assert result.removed_holidays == 1
    assert result.removed_makeup_trading_days == 1
    payload = yaml.safe_load((config_dir / "sync_schedule.yaml").read_text(encoding="utf-8"))
    assert payload["holidays"] == [
        "2025-12-31",
        "2026-01-02",
        "2026-02-02",
    ]
    assert payload["makeup_trading_days"] == [
        "2025-12-28",
        "2026-01-04",
        "2026-02-01",
    ]
    updated_text = (config_dir / "sync_schedule.yaml").read_text(encoding="utf-8")
    assert 'version: "1.0"' in updated_text
    assert '      - start: "09:30"' in updated_text
    assert '        end: "11:30"' in updated_text


def test_run_trade_calendar_sync_fails_when_provider_returns_empty_year(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir()
    (config_dir / "sync_schedule.yaml").write_text(
        """
version: "1.0"
timezone: "Asia/Shanghai"
jobs:
  market_bulk_snapshot:
    interval_minutes: 30
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "dataanalysisbase.delivery.sync.load_settings",
        lambda: Settings(config_dir=config_dir, data_dir=data_dir),
    )

    result = run_trade_calendar_sync(
        config_dir=config_dir,
        provider=MockTradeCalendarProvider({date(2025, 1, 2)}),
        year=2026,
    )

    assert result.status == "failed"
    assert result.errors == ["provider returned 0 trade calendar records for 2026"]


def test_run_industry_mapping_sync_falls_back_to_secondary_provider(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(
        "dataanalysisbase.delivery.sync.load_settings",
        lambda: Settings(config_dir=ROOT_CONFIG, data_dir=data_dir, tushare_token="token"),
    )
    providers = [
        MockIndustryMappingProvider({}, name="akshare"),
        MockIndustryMappingProvider({"600519.SH": "白酒"}, name="tushare"),
    ]
    monkeypatch.setattr(
        "dataanalysisbase.delivery.sync._industry_mapping_providers",
        lambda _providers, *, provider_name, tushare_token: providers,
    )

    result = run_industry_mapping_sync(config_dir=ROOT_CONFIG)

    assert result.status == "success"
    assert result.source == "tushare"
    assert result.records == 1
    assert result.errors == ["akshare: provider returned 0 industry mapping records"]
    assert (data_dir / "industry_mapping.csv").read_text(encoding="utf-8") == (
        "security_id,industry\n600519.SH,白酒\n"
    )


def test_run_industry_mapping_sync_merges_provider_chain_by_priority(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(
        "dataanalysisbase.delivery.sync.load_settings",
        lambda: Settings(config_dir=ROOT_CONFIG, data_dir=data_dir),
    )
    providers = [
        MockIndustryMappingProvider(
            {"920000.BJ": "北交行业", "600519.SH": "高优先级行业"},
            name="akshare",
        ),
        MockIndustryMappingProvider(
            {"600519.SH": "低优先级行业", "300750.SZ": "电池"},
            name="baostock",
        ),
    ]
    monkeypatch.setattr(
        "dataanalysisbase.delivery.sync._industry_mapping_providers",
        lambda _providers, *, provider_name, tushare_token: providers,
    )

    result = run_industry_mapping_sync(config_dir=ROOT_CONFIG)

    assert result.status == "success"
    assert result.source == "akshare,baostock"
    assert result.records == 3
    assert result.errors == []
    assert (data_dir / "industry_mapping.csv").read_text(encoding="utf-8") == (
        "security_id,industry\n"
        "300750.SZ,电池\n"
        "600519.SH,高优先级行业\n"
        "920000.BJ,北交行业\n"
    )


def test_run_industry_mapping_sync_passes_provider_override(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir = tmp_path / "data"
    seen_provider_names: list[str | None] = []
    monkeypatch.setattr(
        "dataanalysisbase.delivery.sync.load_settings",
        lambda: Settings(config_dir=ROOT_CONFIG, data_dir=data_dir, tushare_token="token"),
    )

    def _providers(_providers, *, provider_name: str | None, tushare_token: str | None):
        seen_provider_names.append(provider_name)
        return [MockIndustryMappingProvider({"600519.SH": "白酒"}, name="tushare")]

    monkeypatch.setattr(
        "dataanalysisbase.delivery.sync._industry_mapping_providers",
        _providers,
    )

    result = run_industry_mapping_sync(config_dir=ROOT_CONFIG, provider_name="tushare")

    assert result.status == "success"
    assert result.source == "tushare"
    assert seen_provider_names == ["tushare"]


def test_run_industry_mapping_sync_can_override_to_efinance(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(
        "dataanalysisbase.delivery.sync.load_settings",
        lambda: Settings(config_dir=ROOT_CONFIG, data_dir=data_dir),
    )
    monkeypatch.setattr(
        "dataanalysisbase.delivery.sync.EfinanceAdapter",
        lambda: MockIndustryMappingProvider({"600519.SH": "白酒"}, name="efinance"),
    )

    result = run_industry_mapping_sync(config_dir=ROOT_CONFIG, provider_name="efinance")

    assert result.status == "success"
    assert result.source == "efinance"
    assert result.records == 1


def test_run_industry_mapping_sync_can_override_to_baostock(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(
        "dataanalysisbase.delivery.sync.load_settings",
        lambda: Settings(config_dir=ROOT_CONFIG, data_dir=data_dir),
    )
    monkeypatch.setattr(
        "dataanalysisbase.delivery.sync.BaostockAdapter",
        lambda: MockIndustryMappingProvider({"600519.SH": "白酒"}, name="baostock"),
    )

    result = run_industry_mapping_sync(config_dir=ROOT_CONFIG, provider_name="baostock")

    assert result.status == "success"
    assert result.source == "baostock"
    assert result.records == 1


def test_run_industry_mapping_backfill_updates_latest_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir = tmp_path / "data"
    duckdb_path = tmp_path / "sync.duckdb"
    mapping_path = data_dir / "industry_mapping.csv"
    mapping_path.parent.mkdir(parents=True)
    mapping_path.write_text("security_id,industry\n600519.SH,白酒\n", encoding="utf-8")
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    store = DuckDBStore(duckdb_path)
    store.init_schema()
    snapshot_repo = SnapshotRepo(store)
    aggregate_repo = AggregateRepo(store)
    snapshot_repo.begin_run(snapshot_time, "mock", expected=1)
    snapshot_repo.write_snapshot([_row(snapshot_time, "600519.SH", industry_code=None)])
    snapshot_repo.commit_run(snapshot_time, "mock", RunStatus.SUCCESS, actual=1, missing=0)
    aggregate_repo.refresh_latest(snapshot_time)
    aggregate_repo.refresh_industry(snapshot_time)
    store.close()
    monkeypatch.setattr(
        "dataanalysisbase.delivery.sync.load_settings",
        lambda: Settings(config_dir=ROOT_CONFIG, data_dir=data_dir, duckdb_path=duckdb_path),
    )

    result = run_industry_mapping_backfill(config_dir=ROOT_CONFIG)

    assert result.status == "success"
    assert result.mapping_records == 1
    assert result.backfilled == 1
    store = DuckDBStore(duckdb_path, read_only=True)
    try:
        latest = store.query("SELECT industry_code FROM latest_market_snapshot")
        industries = store.query("SELECT industry_code, stock_count FROM industry_snapshots")
    finally:
        store.close()
    assert latest == [{"industry_code": "白酒"}]
    assert industries == [{"industry_code": "白酒", "stock_count": 1}]


def test_run_industry_mapping_backfill_normalizes_raw_security_codes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir = tmp_path / "data"
    duckdb_path = tmp_path / "sync.duckdb"
    mapping_path = data_dir / "industry_mapping.csv"
    mapping_path.parent.mkdir(parents=True)
    mapping_path.write_text("security_id,industry\n600519,白酒\n", encoding="utf-8")
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    store = DuckDBStore(duckdb_path)
    store.init_schema()
    snapshot_repo = SnapshotRepo(store)
    snapshot_repo.begin_run(snapshot_time, "mock", expected=1)
    snapshot_repo.write_snapshot([_row(snapshot_time, "600519.SH", industry_code=None)])
    snapshot_repo.commit_run(snapshot_time, "mock", RunStatus.SUCCESS, actual=1, missing=0)
    AggregateRepo(store).refresh_latest(snapshot_time)
    store.close()
    monkeypatch.setattr(
        "dataanalysisbase.delivery.sync.load_settings",
        lambda: Settings(config_dir=ROOT_CONFIG, data_dir=data_dir, duckdb_path=duckdb_path),
    )

    result = run_industry_mapping_backfill(config_dir=ROOT_CONFIG)

    assert result.status == "success"
    assert result.mapping_records == 1
    assert result.backfilled == 1


def test_run_industry_mapping_backfill_refreshes_latest_when_no_rows_changed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir = tmp_path / "data"
    duckdb_path = tmp_path / "sync.duckdb"
    mapping_path = data_dir / "industry_mapping.csv"
    mapping_path.parent.mkdir(parents=True)
    mapping_path.write_text("security_id,industry\n600519.SH,白酒\n", encoding="utf-8")
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    store = DuckDBStore(duckdb_path)
    store.init_schema()
    snapshot_repo = SnapshotRepo(store)
    snapshot_repo.begin_run(snapshot_time, "mock", expected=1)
    snapshot_repo.write_snapshot([_row(snapshot_time, "600519.SH", industry_code="白酒")])
    snapshot_repo.commit_run(snapshot_time, "mock", RunStatus.SUCCESS, actual=1, missing=0)
    store.execute(
        """
        UPDATE latest_market_snapshot
        SET industry_code = NULL
        WHERE security_id = ?
        """,
        ["600519.SH"],
    )
    store.close()
    monkeypatch.setattr(
        "dataanalysisbase.delivery.sync.load_settings",
        lambda: Settings(config_dir=ROOT_CONFIG, data_dir=data_dir, duckdb_path=duckdb_path),
    )

    result = run_industry_mapping_backfill(config_dir=ROOT_CONFIG)

    assert result.status == "success"
    assert result.backfilled == 0
    store = DuckDBStore(duckdb_path, read_only=True)
    try:
        latest = store.query("SELECT industry_code FROM latest_market_snapshot")
    finally:
        store.close()
    assert latest == [{"industry_code": "白酒"}]


def test_inspect_industry_mapping_coverage_reports_missing_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir = tmp_path / "data"
    duckdb_path = tmp_path / "sync.duckdb"
    mapping_path = data_dir / "industry_mapping.csv"
    missing_path = tmp_path / "missing.csv"
    mapping_path.parent.mkdir(parents=True)
    mapping_path.write_text("security_id,industry\n600519,白酒\n", encoding="utf-8")
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    store = DuckDBStore(duckdb_path)
    store.init_schema()
    snapshot_repo = SnapshotRepo(store)
    snapshot_repo.begin_run(snapshot_time, "mock", expected=3)
    snapshot_repo.write_snapshot(
        [
            _row(snapshot_time, "600519.SH", industry_code="白酒"),
            _row(snapshot_time, "300750.SZ", industry_code=None),
            _row(snapshot_time, "000001.SZ", industry_code="UNKNOWN"),
        ]
    )
    snapshot_repo.commit_run(snapshot_time, "mock", RunStatus.SUCCESS, actual=3, missing=0)
    AggregateRepo(store).refresh_latest(snapshot_time)
    store.close()
    monkeypatch.setattr(
        "dataanalysisbase.delivery.sync.load_settings",
        lambda: Settings(config_dir=ROOT_CONFIG, data_dir=data_dir, duckdb_path=duckdb_path),
    )

    result = inspect_industry_mapping_coverage(
        config_dir=ROOT_CONFIG,
        missing_output=missing_path,
    )

    assert result.status == "success"
    assert result.total_snapshot_records == 3
    assert result.mapped_snapshot_records == 1
    assert result.unknown_snapshot_records == 2
    assert result.mapping_records == 1
    assert result.missing_mapping_records == 2
    assert result.coverage_ratio == 1 / 3
    assert result.missing_output == str(missing_path)
    assert missing_path.read_text(encoding="utf-8") == (
        "security_id,name,industry\n"
        "000001.SZ,000001.SZ,\n"
        "300750.SZ,300750.SZ,\n"
    )


def test_industry_coverage_cli_outputs_json(tmp_path: Path, monkeypatch, capsys) -> None:
    data_dir = tmp_path / "data"
    duckdb_path = tmp_path / "sync.duckdb"
    mapping_path = data_dir / "industry_mapping.csv"
    mapping_path.parent.mkdir(parents=True)
    mapping_path.write_text("security_id,industry\n600519.SH,白酒\n", encoding="utf-8")
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    store = DuckDBStore(duckdb_path)
    store.init_schema()
    snapshot_repo = SnapshotRepo(store)
    snapshot_repo.begin_run(snapshot_time, "mock", expected=1)
    snapshot_repo.write_snapshot([_row(snapshot_time, "600519.SH", industry_code="白酒")])
    snapshot_repo.commit_run(snapshot_time, "mock", RunStatus.SUCCESS, actual=1, missing=0)
    AggregateRepo(store).refresh_latest(snapshot_time)
    store.close()
    monkeypatch.setattr(
        "dataanalysisbase.delivery.sync.load_settings",
        lambda: Settings(config_dir=ROOT_CONFIG, data_dir=data_dir, duckdb_path=duckdb_path),
    )

    exit_code = main(["industry", "coverage", "--config-dir", str(ROOT_CONFIG), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["task"] == "industry_mapping_coverage"
    assert payload["coverage_ratio"] == 1.0


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
    def __init__(self, mapping: dict[str, str], *, name: str = "mock") -> None:
        self.mapping = mapping
        self.name = name

    def fetch_industry_mapping(self) -> dict[str, str]:
        return self.mapping


class MockTradeCalendarProvider:
    name = "mock"

    def __init__(self, trade_dates: set[date]) -> None:
        self.trade_dates = trade_dates

    def fetch_trade_dates(self) -> set[date]:
        return self.trade_dates


def _row(
    snapshot_time: datetime,
    security_id: str,
    *,
    industry_code: str | None = "TEST",
) -> MarketRow:
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
        industry_code=industry_code,
    )
