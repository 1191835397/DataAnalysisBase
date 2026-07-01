from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dataanalysisbase.domain.contracts import (
    MarketRow,
    MarketSyncJobStatus,
    SurveillanceAlertRecord,
    SyncResult,
)
from dataanalysisbase.domain.enums import AlertSeverity, AlertStatus, RunStatus
from dataanalysisbase.storage import (
    AggregateRepo,
    AlertRepo,
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


def test_snapshot_round_trips_suspended_flag(tmp_path: Path) -> None:
    store = DuckDBStore(tmp_path / "test.duckdb")
    store.init_schema()
    repo = SnapshotRepo(store)
    aggregate_repo = AggregateRepo(store)
    t = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    repo.begin_run(t, "test", expected=1)
    repo.write_snapshot([_row(t, "600519.SH", 1.2, is_suspended=True)])
    repo.commit_run(t, "test", RunStatus.SUCCESS, actual=1, missing=0)
    rows = repo.get_snapshot(t)
    aggregate_repo.refresh_latest(t)
    stock = aggregate_repo.get_stock("600519.SH")

    assert rows[0].is_suspended is True
    assert stock is not None
    assert stock["is_suspended"] is True


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

    stock = aggregate_repo.get_stock("600519.SH")
    assert stock is not None
    assert stock["security_id"] == "600519.SH"
    assert stock["change_pct"] == 10.0
    assert aggregate_repo.get_stock("999999.SH") is None

    industries = aggregate_repo.get_industries(IndustryQuery(limit=1))
    assert len(industries) == 1
    assert industries[0]["industry_code"] == "TEST"
    assert industries[0]["stock_count"] == 2


def test_aggregate_repo_uses_board_specific_limit_thresholds(tmp_path: Path) -> None:
    store = DuckDBStore(tmp_path / "test.duckdb")
    store.init_schema()
    snapshot_repo = SnapshotRepo(store)
    aggregate_repo = AggregateRepo(store)
    t = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    snapshot_repo.begin_run(t, "test", expected=8)
    snapshot_repo.write_snapshot(
        [
            _row(t, "600519.SH", 9.9),
            _row(t, "600000.SH", 5.1, name="ST浦发"),
            _row(t, "600001.SH", 4.8, name="ST未达"),
            _row(t, "688001.SH", 19.9),
            _row(t, "300001.SZ", 10.0),
            _row(t, "300002.SZ", 19.8),
            _row(t, "830001.BJ", 29.9),
            _row(t, "830002.BJ", 20.0),
        ]
    )
    snapshot_repo.commit_run(t, "test", RunStatus.SUCCESS, actual=8, missing=0)
    aggregate_repo.refresh_latest(t)
    aggregate_repo.refresh_overview(t)

    overview = aggregate_repo.get_overview()
    limit_up_page = aggregate_repo.get_stocks_page(StockQuery(size=20, filter="limit_up"))

    assert overview is not None
    assert overview["limit_up_count"] == 4
    assert {item["security_id"] for item in limit_up_page.items} == {
        "600519.SH",
        "600000.SH",
        "688001.SH",
        "830001.BJ",
    }


def test_aggregate_repo_skips_new_listing_limit_thresholds(tmp_path: Path) -> None:
    store = DuckDBStore(tmp_path / "test.duckdb")
    store.init_schema()
    snapshot_repo = SnapshotRepo(store)
    aggregate_repo = AggregateRepo(store)
    t = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    snapshot_repo.begin_run(t, "test", expected=2)
    snapshot_repo.write_snapshot(
        [
            _row(t, "001001.SZ", 30.0, listing_date=date(2026, 6, 20)),
            _row(t, "001002.SZ", 9.9, listing_date=date(2026, 6, 1)),
        ]
    )
    snapshot_repo.commit_run(t, "test", RunStatus.SUCCESS, actual=2, missing=0)
    rows = snapshot_repo.get_snapshot(t)
    aggregate_repo.refresh_latest(t)
    aggregate_repo.refresh_overview(t)

    overview = aggregate_repo.get_overview()
    limit_up_page = aggregate_repo.get_stocks_page(StockQuery(size=20, filter="limit_up"))
    new_stock = aggregate_repo.get_stock("001001.SZ")

    assert rows[0].listing_date == date(2026, 6, 20)
    assert overview is not None
    assert overview["limit_up_count"] == 1
    assert [item["security_id"] for item in limit_up_page.items] == ["001002.SZ"]
    assert new_stock is not None
    assert new_stock["listing_date"] == date(2026, 6, 20)


def test_aggregate_repo_skips_delta_price_for_ex_dividend_rows(tmp_path: Path) -> None:
    store = DuckDBStore(tmp_path / "test.duckdb")
    store.init_schema()
    snapshot_repo = SnapshotRepo(store)
    aggregate_repo = AggregateRepo(store)
    previous = datetime(2026, 6, 23, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    current = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    snapshot_repo.begin_run(previous, "test", expected=1)
    snapshot_repo.write_snapshot(
        [_row(previous, "600519.SH", 1.0, price=100.0, volume_ratio=1.0)]
    )
    snapshot_repo.commit_run(previous, "test", RunStatus.SUCCESS, actual=1, missing=0)
    snapshot_repo.begin_run(current, "test", expected=1)
    snapshot_repo.write_snapshot(
        [
            _row(
                current,
                "600519.SH",
                1.0,
                price=80.0,
                volume_ratio=1.0,
                ex_dividend=True,
            )
        ]
    )
    snapshot_repo.commit_run(current, "test", RunStatus.SUCCESS, actual=1, missing=0)
    rows = snapshot_repo.get_snapshot(current)
    aggregate_repo.refresh_latest(current)

    candidates = aggregate_repo.get_alert_candidates(
        limit_up_threshold=9.9,
        limit_down_threshold=-9.9,
        volume_ratio_threshold=2.0,
        extreme_change_threshold=3.0,
        limit=10,
    )
    stock = aggregate_repo.get_stock("600519.SH")

    assert rows[0].ex_dividend is True
    assert stock is not None
    assert stock["ex_dividend"] is True
    assert candidates == []


def test_aggregate_repo_skips_suspended_alert_candidates(tmp_path: Path) -> None:
    store = DuckDBStore(tmp_path / "test.duckdb")
    store.init_schema()
    snapshot_repo = SnapshotRepo(store)
    aggregate_repo = AggregateRepo(store)
    t = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    snapshot_repo.begin_run(t, "test", expected=1)
    snapshot_repo.write_snapshot(
        [_row(t, "600519.SH", 10.5, volume_ratio=3.5, is_suspended=True)]
    )
    snapshot_repo.commit_run(t, "test", RunStatus.SUCCESS, actual=1, missing=0)
    aggregate_repo.refresh_latest(t)

    candidates = aggregate_repo.get_alert_candidates(
        limit_up_threshold=9.9,
        limit_down_threshold=-9.9,
        volume_ratio_threshold=2.0,
        extreme_change_threshold=3.0,
        limit=10,
    )

    assert candidates == []


def test_aggregate_repo_reads_legacy_snapshot_schema_in_read_only_mode(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "legacy.duckdb"
    store = DuckDBStore(db_path)
    previous = datetime(2026, 6, 23, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    current = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    _create_legacy_market_tables(store)
    store.execute(
        """
        INSERT INTO market_snapshot_runs (snapshot_time, source, status)
        VALUES (?, ?, ?), (?, ?, ?)
        """,
        [
            previous,
            "test",
            RunStatus.SUCCESS.value,
            current,
            "test",
            RunStatus.SUCCESS.value,
        ],
    )
    store.execute(
        """
        INSERT INTO market_snapshots (
            snapshot_time, security_id, name, price, change_pct, volume, amount,
            turnover_rate, volume_ratio, pe_ttm, pb, market_cap, industry_code,
            source, fetched_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            previous,
            "600519.SH",
            "贵州茅台",
            100.0,
            1.0,
            1000.0,
            100000.0,
            0.5,
            1.0,
            20.0,
            3.0,
            1000000.0,
            "TEST",
            "test",
            previous,
        ],
    )
    store.execute(
        """
        INSERT INTO latest_market_snapshot (
            snapshot_time, security_id, name, price, change_pct, volume, amount,
            turnover_rate, volume_ratio, pe_ttm, pb, market_cap, industry_code,
            source, fetched_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            current,
            "600519.SH",
            "贵州茅台",
            110.0,
            1.0,
            1000.0,
            100000.0,
            0.5,
            1.0,
            20.0,
            3.0,
            1000000.0,
            "TEST",
            "test",
            current,
        ],
    )
    store.close()

    read_store = DuckDBStore(db_path, read_only=True)
    repo = AggregateRepo(read_store)

    stock = repo.get_stock("600519.SH")
    candidates = repo.get_alert_candidates(
        limit_up_threshold=9.9,
        limit_down_threshold=-9.9,
        volume_ratio_threshold=2.0,
        extreme_change_threshold=3.0,
        limit=10,
    )

    assert stock is not None
    assert stock["listing_date"] is None
    assert stock["ex_dividend"] is False
    assert stock["is_suspended"] is False
    assert len(candidates) == 1
    assert candidates[0]["is_suspended"] is False
    assert candidates[0]["delta_price_pct"] == 10.0
    read_store.close()


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
        artifact_path="data/artifacts/sync/job-1.json",
    )

    repo.upsert(job)

    loaded = repo.get("job-1")
    latest = repo.latest()
    recent = repo.list_recent(10)
    assert loaded is not None
    assert loaded.job_id == "job-1"
    assert loaded.result is not None
    assert loaded.result.actual == 2
    assert loaded.elapsed_seconds == 12
    assert loaded.artifact_path == "data/artifacts/sync/job-1.json"
    assert latest is not None
    assert latest.job_id == "job-1"
    assert [item.job_id for item in recent] == ["job-1"]


def test_sync_job_repo_lists_recent_jobs_by_created_at(tmp_path: Path) -> None:
    store = DuckDBStore(tmp_path / "test.duckdb")
    store.init_schema()
    repo = SyncJobRepo(store)
    first_at = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    second_at = datetime(2026, 6, 23, 10, 35, tzinfo=ZoneInfo("Asia/Shanghai"))

    repo.upsert(
        MarketSyncJobStatus(
            job_id="job-1",
            status=RunStatus.SUCCESS,
            created_at=first_at,
            finished_at=first_at,
            result=_sync_result(first_at, actual=1),
        )
    )
    repo.upsert(
        MarketSyncJobStatus(
            job_id="job-2",
            status=RunStatus.PARTIAL,
            created_at=second_at,
            finished_at=second_at,
            result=_sync_result(second_at, actual=2),
        )
    )

    recent = repo.list_recent(1)

    assert [job.job_id for job in recent] == ["job-2"]
    assert recent[0].result is not None
    assert recent[0].result.actual == 2


def test_sync_job_repo_pages_jobs_and_summarizes_failures(tmp_path: Path) -> None:
    store = DuckDBStore(tmp_path / "test.duckdb")
    store.init_schema()
    repo = SyncJobRepo(store)
    first_at = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    second_at = datetime(2026, 6, 23, 10, 35, tzinfo=ZoneInfo("Asia/Shanghai"))
    third_at = datetime(2026, 6, 23, 10, 40, tzinfo=ZoneInfo("Asia/Shanghai"))
    repo.upsert(
        MarketSyncJobStatus(
            job_id="job-1",
            status=RunStatus.SUCCESS,
            created_at=first_at,
            finished_at=first_at,
            result=_sync_result(first_at, actual=1),
        )
    )
    repo.upsert(
        MarketSyncJobStatus(
            job_id="job-2",
            status=RunStatus.FAILED,
            created_at=second_at,
            finished_at=second_at,
            error="provider timeout",
        )
    )
    repo.upsert(
        MarketSyncJobStatus(
            job_id="job-3",
            status=RunStatus.PARTIAL,
            created_at=third_at,
            finished_at=third_at,
            result=_sync_result(third_at, actual=2),
        )
    )

    jobs, total = repo.list_page(page=2, size=2)
    summary = repo.failure_summary(recent=3)

    assert total == 3
    assert [job.job_id for job in jobs] == ["job-1"]
    assert summary["total"] == 3
    assert summary["failed"] == 1
    assert summary["partial"] == 1
    assert summary["latest_failed_at"] == second_at


def test_alert_repo_persists_lifecycle_status_and_trigger_count(tmp_path: Path) -> None:
    store = DuckDBStore(tmp_path / "test.duckdb")
    store.init_schema()
    repo = AlertRepo(store)
    first_at = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    later_at = datetime(2026, 6, 23, 10, 35, tzinfo=ZoneInfo("Asia/Shanghai"))
    alert = _alert("limit_up:600519.SH", first_at)

    repo.upsert_many([alert])
    repo.update_status(alert.alert_id, AlertStatus.HANDLED)
    repo.upsert_many([alert])

    loaded = repo.get(alert.alert_id)
    assert loaded is not None
    assert loaded.status == AlertStatus.HANDLED
    assert loaded.trigger_count == 1

    repo.upsert_many(
        [
            alert.model_copy(
                update={
                    "message": "new value",
                    "last_triggered_at": later_at,
                    "value": 10.5,
                }
            )
        ]
    )

    refreshed = repo.get(alert.alert_id)
    assert refreshed is not None
    assert refreshed.status == AlertStatus.NEW
    assert refreshed.trigger_count == 2
    assert refreshed.message == "new value"
    assert [item.alert_id for item in repo.list_recent(limit=10)] == [alert.alert_id]
    assert [item.alert_id for item in repo.list_for_security("600519.SH", limit=10)] == [
        alert.alert_id
    ]
    assert repo.list_for_security("999999.SH", limit=10) == []


def _row(
    snapshot_time: datetime,
    security_id: str,
    change_pct: float,
    *,
    name: str | None = None,
    industry_code: str | None = "TEST",
    price: float = 100.0,
    volume_ratio: float = 2.2,
    listing_date: date | None = None,
    ex_dividend: bool = False,
    is_suspended: bool = False,
) -> MarketRow:
    return MarketRow(
        snapshot_time=snapshot_time,
        security_id=security_id,
        name=name or security_id,
        price=price,
        change_pct=change_pct,
        volume=1000,
        amount=100000,
        volume_ratio=volume_ratio,
        pe_ttm=20,
        pb=3,
        market_cap=1000000,
        industry_code=industry_code,
        listing_date=listing_date,
        ex_dividend=ex_dividend,
        is_suspended=is_suspended,
        source="test",
        fetched_at=snapshot_time,
    )


def _alert(alert_id: str, triggered_at: datetime) -> SurveillanceAlertRecord:
    return SurveillanceAlertRecord(
        alert_id=alert_id,
        rule_id="limit_up",
        severity=AlertSeverity.HIGH,
        kind="limit_up",
        status=AlertStatus.NEW,
        title="涨停告警",
        message="贵州茅台(600519.SH) change_pct=10.00, 阈值 9.90",
        first_triggered_at=triggered_at,
        last_triggered_at=triggered_at,
        security_id="600519.SH",
        name="贵州茅台",
        industry_code="TEST",
        metric="change_pct",
        value=10.0,
        threshold=9.9,
        snapshot_time=triggered_at,
        source="test",
    )


def _create_legacy_market_tables(store: DuckDBStore) -> None:
    store.execute(
        """
        CREATE TABLE market_snapshot_runs (
            snapshot_time TIMESTAMPTZ NOT NULL,
            source VARCHAR NOT NULL,
            status VARCHAR NOT NULL
        )
        """
    )
    store.execute(
        """
        CREATE TABLE market_snapshots (
            snapshot_time TIMESTAMPTZ NOT NULL,
            security_id VARCHAR NOT NULL,
            name VARCHAR NOT NULL,
            price DOUBLE,
            change_pct DOUBLE,
            volume DOUBLE,
            amount DOUBLE,
            turnover_rate DOUBLE,
            volume_ratio DOUBLE,
            pe_ttm DOUBLE,
            pb DOUBLE,
            market_cap DOUBLE,
            industry_code VARCHAR,
            source VARCHAR NOT NULL,
            fetched_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    store.execute(
        """
        CREATE TABLE latest_market_snapshot (
            snapshot_time TIMESTAMPTZ NOT NULL,
            security_id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            price DOUBLE,
            change_pct DOUBLE,
            volume DOUBLE,
            amount DOUBLE,
            turnover_rate DOUBLE,
            volume_ratio DOUBLE,
            pe_ttm DOUBLE,
            pb DOUBLE,
            market_cap DOUBLE,
            industry_code VARCHAR,
            source VARCHAR NOT NULL,
            fetched_at TIMESTAMPTZ NOT NULL
        )
        """
    )


def _sync_result(snapshot_time: datetime, *, actual: int) -> SyncResult:
    return SyncResult(
        task="market_bulk_sync",
        status=RunStatus.SUCCESS,
        expected=actual,
        actual=actual,
        missing=0,
        snapshot_time=snapshot_time,
    )
