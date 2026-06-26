"""Repository for market snapshots and snapshot runs."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from dataanalysisbase.domain.contracts import MarketRow
from dataanalysisbase.domain.enums import RunStatus
from dataanalysisbase.storage.repositories.base import BaseRepo


class SnapshotRepo(BaseRepo):
    """Write and read market snapshot data."""

    def begin_run(self, snapshot_time: datetime, source: str, expected: int) -> None:
        self.store.execute(
            """
            INSERT OR REPLACE INTO market_snapshot_runs (
                snapshot_time, source, status, expected, actual, missing, field_nulls,
                error, started_at, finished_at
            )
            VALUES (?, ?, ?, ?, 0, 0, NULL, NULL, now(), NULL)
            """,
            [snapshot_time, source, RunStatus.RUNNING.value, expected],
        )

    def write_snapshot(self, rows: list[MarketRow]) -> int:
        if not rows:
            return 0

        values = [_market_row_values(row) for row in rows]
        with self.store.transaction() as conn:
            conn.executemany(
                """
                DELETE FROM market_snapshots
                WHERE snapshot_time = ? AND security_id = ? AND source = ?
                """,
                [(row.snapshot_time, row.security_id, row.source) for row in rows],
            )
            conn.executemany(
                """
                INSERT INTO market_snapshots (
                    snapshot_time, security_id, name, price, change_pct, volume, amount,
                    turnover_rate, volume_ratio, pe_ttm, pb, market_cap, industry_code,
                    source, fetched_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
        return len(rows)

    def commit_run(
        self,
        snapshot_time: datetime,
        source: str,
        status: RunStatus,
        *,
        actual: int,
        missing: int,
        field_nulls: dict[str, int] | None = None,
        error: str | None = None,
    ) -> None:
        self.store.execute(
            """
            UPDATE market_snapshot_runs
            SET status = ?, actual = ?, missing = ?, field_nulls = ?::JSON,
                error = ?, finished_at = now()
            WHERE snapshot_time = ? AND source = ?
            """,
            [
                status.value,
                actual,
                missing,
                json.dumps(field_nulls or {}, ensure_ascii=False),
                error,
                snapshot_time,
                source,
            ],
        )

    def latest_committed(self) -> datetime | None:
        rows = self.store.query(
            """
            SELECT snapshot_time
            FROM market_snapshot_runs
            WHERE status IN (?, ?)
            ORDER BY snapshot_time DESC
            LIMIT 1
            """,
            [RunStatus.SUCCESS.value, RunStatus.PARTIAL.value],
        )
        return rows[0]["snapshot_time"] if rows else None

    def latest_run(self) -> dict[str, Any] | None:
        rows = self.store.query(
            """
            SELECT snapshot_time, source, status, expected, actual, missing,
                   error, started_at, finished_at
            FROM market_snapshot_runs
            ORDER BY started_at DESC
            LIMIT 1
            """
        )
        return rows[0] if rows else None

    def get_snapshot(self, snapshot_time: datetime) -> list[MarketRow]:
        rows = self.store.query(
            """
            SELECT snapshot_time, security_id, name, price, change_pct, volume, amount,
                   turnover_rate, volume_ratio, pe_ttm, pb, market_cap, industry_code,
                   source, fetched_at
            FROM market_snapshots
            WHERE snapshot_time = ?
            ORDER BY security_id
            """,
            [snapshot_time],
        )
        return [MarketRow.model_validate(row) for row in rows]

    def previous_snapshot_time(self, before: datetime) -> datetime | None:
        rows = self.store.query(
            """
            SELECT snapshot_time
            FROM market_snapshot_runs
            WHERE snapshot_time < ? AND status IN (?, ?)
            ORDER BY snapshot_time DESC
            LIMIT 1
            """,
            [before, RunStatus.SUCCESS.value, RunStatus.PARTIAL.value],
        )
        return rows[0]["snapshot_time"] if rows else None


def _market_row_values(row: MarketRow) -> list[Any]:
    return [
        row.snapshot_time,
        row.security_id,
        row.name,
        row.price,
        row.change_pct,
        row.volume,
        row.amount,
        row.turnover_rate,
        row.volume_ratio,
        row.pe_ttm,
        row.pb,
        row.market_cap,
        row.industry_code,
        row.source,
        row.fetched_at,
    ]
