from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dataanalysisbase.domain.contracts import MarketRow, MarketSyncJobStatus, SyncResult
from dataanalysisbase.domain.enums import RunStatus
from dataanalysisbase.storage import (
    AggregateRepo,
    DuckDBStore,
    IndustryQuery,
    SnapshotRepo,
    StockQuery,
    SyncJobRepo,
)


def test_snapshot_write_is_idempotent(tmp_path: Path) -> None:
    store = DuckDBStore(tmp_path / "test.duckdb")
    store.init_schema()
    repo = SnapshotRepo(store)
    t = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    row = _row(t, "600519.SH", 1.2)

    repo.begin_run(t, "test", expected=1)
    assert repo.write_snapshot([row]) == 1
    assert repo.write_snapshot([row]) == 1
    repo.commit_run(t, "test", RunStatus.SUCCESS, actual=1, missing=0)

    rows = repo.get_snapshot(t)
    assert len(rows) == 1
    assert rows[0].security_id == "600519.SH"
    assert repo.latest_committed() == t
    latest_run = repo.latest_run()
    assert latest_run is not None
    assert latest_run["status"] == RunStatus.SUCCESS.value
    assert latest_run["actual"] == 1


def test_aggregate_repo_refreshes_overview_and_stock_page(tmp_path: Path) -> None:
    store = DuckDBStore(tmp_path / "test.duckdb")
    store.init_schema()
    snapshot_repo = SnapshotRepo(store)
    aggregate_repo = AggregateRepo(store)
    t = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    snapshot_repo.begin_run(t, "test", expected=2)
    snapshot_repo.write_snapshot([_row(t, "600519.SH", 10.0), _row(t, "300750.SZ", -2.0)])
    snapshot_repo.commit_run(t, "test", RunStatus.SUCCESS, actual=2, missing=0)

    aggregate_repo.refresh_latest(t)
    aggregate_repo.refresh_overview(t)
    aggregate_repo.refresh_industry(t)

    overview = aggregate_repo.get_overview()
    assert overview is not None
    assert overview["stock_count"] == 2
    assert overview["up_count"] == 1

    page = aggregate_repo.get_stocks_page(StockQuery(size=1, filter="gainers"))
    assert page.total == 1
    assert page.items[0]["security_id"] == "600519.SH"

    industries = aggregate_repo.get_industries(IndustryQuery(limit=1))
    assert len(industries) == 1
    assert industries[0]["industry_code"] == "TEST"
    assert industries[0]["stock_count"] == 2


def test_stock_query_unknown_industry_matches_null_industry(tmp_path: Path) -> None:
    store = DuckDBStore(tmp_path / "test.duckdb")
    store.init_schema()
    snapshot_repo = SnapshotRepo(store)
    aggregate_repo = AggregateRepo(store)
    t = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    snapshot_repo.begin_run(t, "test", expected=1)
    snapshot_repo.write_snapshot([_row(t, "600519.SH", 1.2, industry_code=None)])
    snapshot_repo.commit_run(t, "test", RunStatus.SUCCESS, actual=1, missing=0)
    aggregate_repo.refresh_latest(t)

    page = aggregate_repo.get_stocks_page(StockQuery(industry="UNKNOWN"))

    assert page.total == 1
    assert page.items[0]["security_id"] == "600519.SH"
    assert page.items[0]["industry_code"] is None


def test_sync_job_repo_round_trips_latest_job(tmp_path: Path) -> None:
    store = DuckDBStore(tmp_path / "test.duckdb")
    store.init_schema()
    repo = SyncJobRepo(store)
    created_at = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    job = MarketSyncJobStatus(
        job_id="job-1",
        status=RunStatus.SUCCESS,
        created_at=created_at,
        started_at=created_at,
        finished_at=created_at,
        result=SyncResult(
            task="market_bulk_sync",
            status=RunStatus.SUCCESS,
            expected=2,
            actual=2,
            missing=0,
            snapshot_time=created_at,
        ),
        message="done",
        elapsed_seconds=12,
    )

    repo.upsert(job)

    loaded = repo.get("job-1")
    latest = repo.latest()
    assert loaded is not None
    assert loaded.job_id == "job-1"
    assert loaded.result is not None
    assert loaded.result.actual == 2
    assert loaded.elapsed_seconds == 12
    assert latest is not None
    assert latest.job_id == "job-1"


def _row(
    snapshot_time: datetime,
    security_id: str,
    change_pct: float,
    *,
    industry_code: str | None = "TEST",
) -> MarketRow:
    return MarketRow(
        snapshot_time=snapshot_time,
        security_id=security_id,
        name=security_id,
        price=100.0,
        change_pct=change_pct,
        volume=1000,
        amount=100000,
        volume_ratio=2.2,
        pe_ttm=20,
        pb=3,
        market_cap=1000000,
        industry_code=industry_code,
        source="test",
        fetched_at=snapshot_time,
    )
