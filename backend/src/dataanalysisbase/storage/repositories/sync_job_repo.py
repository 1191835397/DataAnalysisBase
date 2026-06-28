"""Repository for API-triggered sync jobs."""

from __future__ import annotations

import json
from typing import Any

from dataanalysisbase.domain.contracts import MarketSyncJobStatus
from dataanalysisbase.domain.enums import RunStatus
from dataanalysisbase.storage.repositories.base import BaseRepo


class SyncJobRepo(BaseRepo):
    """Persist observable API sync job state."""

    def upsert(self, job: MarketSyncJobStatus) -> None:
        self.store.execute(
            """
            INSERT OR REPLACE INTO api_sync_jobs (
                job_id, status, created_at, started_at, finished_at, result, error,
                cancel_requested, message, elapsed_seconds, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?::JSON, ?, ?, ?, ?, now())
            """,
            [
                job.job_id,
                job.status.value,
                job.created_at,
                job.started_at,
                job.finished_at,
                json.dumps(job.result.model_dump(mode="json") if job.result else None),
                job.error,
                job.cancel_requested,
                job.message,
                job.elapsed_seconds,
            ],
        )

    def latest(self) -> MarketSyncJobStatus | None:
        rows = self.store.query(
            """
            SELECT job_id, status, created_at, started_at, finished_at, result, error,
                   cancel_requested, message, elapsed_seconds
            FROM api_sync_jobs
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        return _row_to_job(rows[0]) if rows else None

    def list_recent(self, limit: int) -> list[MarketSyncJobStatus]:
        rows = self.store.query(
            """
            SELECT job_id, status, created_at, started_at, finished_at, result, error,
                   cancel_requested, message, elapsed_seconds
            FROM api_sync_jobs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            [max(limit, 1)],
        )
        return [_row_to_job(row) for row in rows]

    def get(self, job_id: str) -> MarketSyncJobStatus | None:
        rows = self.store.query(
            """
            SELECT job_id, status, created_at, started_at, finished_at, result, error,
                   cancel_requested, message, elapsed_seconds
            FROM api_sync_jobs
            WHERE job_id = ?
            """,
            [job_id],
        )
        return _row_to_job(rows[0]) if rows else None

    def mark_interrupted_running(self) -> None:
        self.store.execute(
            """
            UPDATE api_sync_jobs
            SET status = ?, error = ?, message = ?, finished_at = now(), updated_at = now()
            WHERE status = ?
            """,
            [
                RunStatus.FAILED.value,
                "market sync interrupted by API restart",
                "同步被 API 重启中断",
                RunStatus.RUNNING.value,
            ],
        )


def _row_to_job(row: dict[str, Any]) -> MarketSyncJobStatus:
    result = row.get("result")
    if isinstance(result, str):
        row["result"] = json.loads(result) if result != "null" else None
    return MarketSyncJobStatus.model_validate(row)
