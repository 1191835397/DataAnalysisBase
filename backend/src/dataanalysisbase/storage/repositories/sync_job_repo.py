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
        self._ensure_artifact_column()
        self.store.execute(
            """
            INSERT OR REPLACE INTO api_sync_jobs (
                job_id, status, created_at, started_at, finished_at, result, error,
                cancel_requested, message, elapsed_seconds, artifact_path, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?::JSON, ?, ?, ?, ?, ?, now())
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
                job.artifact_path,
            ],
        )

    def latest(self) -> MarketSyncJobStatus | None:
        self._ensure_artifact_column()
        rows = self.store.query(
            """
            SELECT job_id, status, created_at, started_at, finished_at, result, error,
                   cancel_requested, message, elapsed_seconds, artifact_path
            FROM api_sync_jobs
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        return _row_to_job(rows[0]) if rows else None

    def list_recent(self, limit: int) -> list[MarketSyncJobStatus]:
        self._ensure_artifact_column()
        rows = self.store.query(
            """
            SELECT job_id, status, created_at, started_at, finished_at, result, error,
                   cancel_requested, message, elapsed_seconds, artifact_path
            FROM api_sync_jobs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            [max(limit, 1)],
        )
        return [_row_to_job(row) for row in rows]

    def list_page(self, *, page: int, size: int) -> tuple[list[MarketSyncJobStatus], int]:
        self._ensure_artifact_column()
        safe_page = max(page, 1)
        safe_size = max(size, 1)
        offset = (safe_page - 1) * safe_size
        total_rows = self.store.query("SELECT count(*) AS total FROM api_sync_jobs")
        rows = self.store.query(
            """
            SELECT job_id, status, created_at, started_at, finished_at, result, error,
                   cancel_requested, message, elapsed_seconds, artifact_path
            FROM api_sync_jobs
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            [safe_size, offset],
        )
        return [_row_to_job(row) for row in rows], int(total_rows[0]["total"])

    def failure_summary(self, *, recent: int) -> dict[str, Any]:
        self._ensure_artifact_column()
        safe_recent = max(recent, 1)
        rows = self.store.query(
            """
            SELECT
                count(*)::INTEGER AS total,
                sum(CASE WHEN status = ? THEN 1 ELSE 0 END)::INTEGER AS failed,
                sum(CASE WHEN status = ? THEN 1 ELSE 0 END)::INTEGER AS partial,
                max(CASE WHEN status = ? THEN created_at ELSE NULL END) AS latest_failed_at
            FROM (
                SELECT status, created_at
                FROM api_sync_jobs
                ORDER BY created_at DESC
                LIMIT ?
            ) recent_jobs
            """,
            [
                RunStatus.FAILED.value,
                RunStatus.PARTIAL.value,
                RunStatus.FAILED.value,
                safe_recent,
            ],
        )
        return rows[0] if rows else {
            "total": 0,
            "failed": 0,
            "partial": 0,
            "latest_failed_at": None,
        }

    def get(self, job_id: str) -> MarketSyncJobStatus | None:
        self._ensure_artifact_column()
        rows = self.store.query(
            """
            SELECT job_id, status, created_at, started_at, finished_at, result, error,
                   cancel_requested, message, elapsed_seconds, artifact_path
            FROM api_sync_jobs
            WHERE job_id = ?
            """,
            [job_id],
        )
        return _row_to_job(rows[0]) if rows else None

    def mark_interrupted_running(self) -> None:
        self._ensure_artifact_column()
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

    def _ensure_artifact_column(self) -> None:
        rows = self.store.query(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'api_sync_jobs'
              AND column_name = 'artifact_path'
            """
        )
        if rows:
            return
        self.store.execute("ALTER TABLE api_sync_jobs ADD COLUMN artifact_path TEXT")


def _row_to_job(row: dict[str, Any]) -> MarketSyncJobStatus:
    result = row.get("result")
    if isinstance(result, str):
        row["result"] = json.loads(result) if result != "null" else None
    return MarketSyncJobStatus.model_validate(row)
