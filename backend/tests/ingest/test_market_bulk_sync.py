from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dataanalysisbase.domain.contracts import MarketRow
from dataanalysisbase.domain.enums import RunStatus
from dataanalysisbase.ingest import MarketBulkSync
from dataanalysisbase.providers import MarketSnapshotBatch
from dataanalysisbase.storage import AggregateRepo, DuckDBStore, SnapshotRepo


def test_market_bulk_sync_success_refreshes_aggregates(tmp_path: Path) -> None:
    sync, store, snapshot_time = _sync(tmp_path, _provider(expected=2, row_count=2))

    result = sync.run_once(snapshot_time)

    assert result.status == RunStatus.SUCCESS
    assert result.expected == 2
    assert result.actual == 2
    assert result.missing == 0
    assert _run_status(store, snapshot_time) == {
        "status": RunStatus.SUCCESS.value,
        "actual": 2,
        "missing": 0,
    }
    overview = AggregateRepo(store).get_overview(snapshot_time)
    assert overview is not None
    assert overview["stock_count"] == 2


def test_market_bulk_sync_partial_records_missing_and_null_fields(tmp_path: Path) -> None:
    sync, store, snapshot_time = _sync(
        tmp_path,
        _provider(expected=3, row_count=2, null_price=True),
    )

    result = sync.run_once(snapshot_time)

    assert result.status == RunStatus.PARTIAL
    assert result.actual == 2
    assert result.missing == 1

    rows = store.query(
        """
        SELECT status, actual, missing, field_nulls
        FROM market_snapshot_runs
        WHERE snapshot_time = ? AND source = ?
        """,
        [snapshot_time, "mock"],
    )
    assert rows[0]["status"] == RunStatus.PARTIAL.value
    assert rows[0]["actual"] == 2
    assert rows[0]["missing"] == 1
    field_nulls = json.loads(rows[0]["field_nulls"])
    assert field_nulls["price"] == 1


def test_market_bulk_sync_failed_provider_records_failed_run(tmp_path: Path) -> None:
    sync, store, snapshot_time = _sync(tmp_path, FailingProvider())

    result = sync.run_once(snapshot_time)

    assert result.status == RunStatus.FAILED
    assert result.actual == 0
    assert result.errors == ["mock fetch failed"]
    rows = store.query(
        """
        SELECT status, actual, missing, error
        FROM market_snapshot_runs
        WHERE snapshot_time = ? AND source = ?
        """,
        [snapshot_time, "mock"],
    )
    assert rows == [
        {
            "status": RunStatus.FAILED.value,
            "actual": 0,
            "missing": 0,
            "error": "mock fetch failed",
        }
    ]


def test_market_bulk_sync_is_idempotent_for_repeated_snapshot(tmp_path: Path) -> None:
    sync, store, snapshot_time = _sync(tmp_path, _provider(expected=2, row_count=2))

    first = sync.run_once(snapshot_time)
    second = sync.run_once(snapshot_time)

    assert first.status == RunStatus.SUCCESS
    assert second.status == RunStatus.SUCCESS
    rows = store.query("SELECT count(*) AS count FROM market_snapshots")
    assert rows[0]["count"] == 2
    overview = AggregateRepo(store).get_overview(snapshot_time)
    assert overview is not None
    assert overview["stock_count"] == 2


class MockProvider:
    name = "mock"

    def __init__(self, *, expected: int, rows: list[MarketRow]) -> None:
        self.expected = expected
        self.rows = rows

    def fetch_market_snapshot(self, snapshot_time: datetime) -> MarketSnapshotBatch:
        return MarketSnapshotBatch(
            snapshot_time=snapshot_time,
            source=self.name,
            expected=self.expected,
            rows=self.rows,
        )


class FailingProvider:
    name = "mock"

    def fetch_market_snapshot(self, snapshot_time: datetime) -> MarketSnapshotBatch:
        raise RuntimeError("mock fetch failed")


def _sync(
    tmp_path: Path,
    provider: MockProvider | FailingProvider,
) -> tuple[MarketBulkSync, DuckDBStore, datetime]:
    store = DuckDBStore(tmp_path / "test.duckdb")
    store.init_schema()
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    return (
        MarketBulkSync(provider, SnapshotRepo(store), AggregateRepo(store)),
        store,
        snapshot_time,
    )


def _provider(*, expected: int, row_count: int, null_price: bool = False) -> MockProvider:
    snapshot_time = datetime(2026, 6, 23, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    rows = [
        _row(
            snapshot_time,
            f"00000{index}.SZ",
            price=None if null_price and index == 1 else 10.0 + index,
            change_pct=float(index),
        )
        for index in range(1, row_count + 1)
    ]
    return MockProvider(expected=expected, rows=rows)


def _row(
    snapshot_time: datetime,
    security_id: str,
    *,
    price: float | None,
    change_pct: float,
) -> MarketRow:
    return MarketRow(
        snapshot_time=snapshot_time,
        security_id=security_id,
        name=security_id,
        price=price,
        change_pct=change_pct,
        volume=1000,
        amount=100000,
        volume_ratio=2.2,
        pe_ttm=20,
        pb=3,
        market_cap=1000000,
        industry_code="TEST",
        source="mock",
        fetched_at=snapshot_time,
    )


def _run_status(store: DuckDBStore, snapshot_time: datetime) -> dict[str, int | str]:
    rows = store.query(
        """
        SELECT status, actual, missing
        FROM market_snapshot_runs
        WHERE snapshot_time = ? AND source = ?
        """,
        [snapshot_time, "mock"],
    )
    assert len(rows) == 1
    return rows[0]
