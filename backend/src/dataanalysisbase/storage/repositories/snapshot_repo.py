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

        self._ensure_snapshot_columns()
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
                    listing_date, ex_dividend, is_suspended, source, fetched_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        self._ensure_snapshot_columns()
        rows = self.store.query(
            """
            SELECT snapshot_time, security_id, name, price, change_pct, volume, amount,
                   turnover_rate, volume_ratio, pe_ttm, pb, market_cap, industry_code,
                   listing_date, coalesce(ex_dividend, FALSE) AS ex_dividend,
                   coalesce(is_suspended, FALSE) AS is_suspended, source, fetched_at
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

    def backfill_industries(
        self,
        snapshot_time: datetime,
        industry_by_security: dict[str, str],
    ) -> int:
        """Backfill missing industry codes for one snapshot from a local mapping."""

        if not industry_by_security:
            return 0

        values = [
            (industry, snapshot_time, security_id)
            for security_id, industry in industry_by_security.items()
            if industry
        ]
        if not values:
            return 0

        missing_rows = self.store.query(
            """
            SELECT security_id
            FROM market_snapshots
            WHERE snapshot_time = ?
              AND (industry_code IS NULL OR industry_code = 'UNKNOWN' OR industry_code = '')
            """,
            [snapshot_time],
        )
        backfilled = sum(
            1 for row in missing_rows if row["security_id"] in industry_by_security
        )
        if backfilled == 0:
            return 0

        with self.store.transaction() as conn:
            conn.executemany(
                """
                UPDATE market_snapshots
                SET industry_code = ?
                WHERE snapshot_time = ?
                  AND security_id = ?
                  AND (industry_code IS NULL OR industry_code = 'UNKNOWN' OR industry_code = '')
                """,
                values,
            )
        return backfilled

    def _ensure_snapshot_columns(self) -> None:
        _ensure_column(self.store, "market_snapshots", "listing_date", "DATE")
        _ensure_column(
            self.store,
            "market_snapshots",
            "ex_dividend",
            "BOOLEAN",
        )
        _ensure_column(
            self.store,
            "market_snapshots",
            "is_suspended",
            "BOOLEAN",
        )


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
        row.listing_date,
        row.ex_dividend,
        row.is_suspended,
        row.source,
        row.fetched_at,
    ]


def _ensure_column(store: Any, table_name: str, column_name: str, column_type: str) -> None:
    rows = store.query(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = ?
          AND column_name = ?
        """,
        [table_name, column_name],
    )
    if rows:
        return
    store.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
