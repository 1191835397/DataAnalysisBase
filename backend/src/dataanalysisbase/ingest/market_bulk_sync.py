"""Whole-market snapshot ingestion workflow."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from dataanalysisbase.domain.contracts import SyncResult
from dataanalysisbase.domain.enums import RunStatus
from dataanalysisbase.providers.market import MarketDataProvider, MarketSnapshotBatch
from dataanalysisbase.storage import AggregateRepo, SnapshotRepo


class MarketBulkSync:
    """Coordinate provider fetches, snapshot writes, and aggregate refreshes."""

    def __init__(
        self,
        provider: MarketDataProvider,
        snapshot_repo: SnapshotRepo,
        aggregate_repo: AggregateRepo,
    ) -> None:
        self.provider = provider
        self.snapshot_repo = snapshot_repo
        self.aggregate_repo = aggregate_repo

    def run_once(self, snapshot_time: datetime) -> SyncResult:
        """Run one whole-market snapshot sync."""

        try:
            batch = self.provider.fetch_market_snapshot(snapshot_time)
        except Exception as exc:
            self.snapshot_repo.begin_run(snapshot_time, self.provider.name, expected=0)
            self.snapshot_repo.commit_run(
                snapshot_time,
                self.provider.name,
                RunStatus.FAILED,
                actual=0,
                missing=0,
                error=str(exc),
            )
            return SyncResult(
                task="market_bulk_sync",
                status=RunStatus.FAILED,
                expected=0,
                actual=0,
                missing=0,
                snapshot_time=snapshot_time,
                errors=[str(exc)],
            )

        return self._commit_batch(batch)

    def _commit_batch(self, batch: MarketSnapshotBatch) -> SyncResult:
        self.snapshot_repo.begin_run(batch.snapshot_time, batch.source, expected=batch.expected)
        actual = self.snapshot_repo.write_snapshot(batch.rows)
        missing = max(batch.expected - actual, 0)
        field_nulls = _count_field_nulls(batch.rows)
        status = _status_for_batch(batch.expected, actual)

        self.snapshot_repo.commit_run(
            batch.snapshot_time,
            batch.source,
            status,
            actual=actual,
            missing=missing,
            field_nulls=field_nulls,
        )

        if actual > 0:
            self.aggregate_repo.refresh_latest(batch.snapshot_time)
            self.aggregate_repo.refresh_overview(batch.snapshot_time)
            self.aggregate_repo.refresh_industry(batch.snapshot_time)

        return SyncResult(
            task="market_bulk_sync",
            status=status,
            expected=batch.expected,
            actual=actual,
            missing=missing,
            snapshot_time=batch.snapshot_time,
        )


def _status_for_batch(expected: int, actual: int) -> RunStatus:
    if actual == 0:
        return RunStatus.FAILED
    return RunStatus.SUCCESS if actual >= expected else RunStatus.PARTIAL


def _count_field_nulls(rows: Sequence[object]) -> dict[str, int]:
    nullable_fields = (
        "price",
        "change_pct",
        "volume",
        "amount",
        "turnover_rate",
        "volume_ratio",
        "pe_ttm",
        "pb",
        "market_cap",
        "industry_code",
    )
    return {
        field: sum(1 for row in rows if getattr(row, field) is None) for field in nullable_fields
    }
