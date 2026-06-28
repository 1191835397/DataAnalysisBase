"""In-process sync job tracking for API-triggered operations."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from threading import Lock
from uuid import uuid4

from fastapi import BackgroundTasks
from pydantic import BaseModel

from dataanalysisbase.domain.contracts import SyncResult
from dataanalysisbase.domain.enums import RunStatus

MarketSyncFn = Callable[[datetime], SyncResult]


class MarketSyncJobStatus(BaseModel):
    """Observable state for one API-triggered market sync job."""

    job_id: str
    status: RunStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: SyncResult | None = None
    error: str | None = None
    elapsed_seconds: int = 0
    message: str = "正在抓取 AKShare 全市场快照"

    def with_runtime_fields(self) -> MarketSyncJobStatus:
        elapsed_seconds = _elapsed_seconds(self)
        return self.model_copy(
            update={
                "elapsed_seconds": elapsed_seconds,
                "message": _job_message(self, elapsed_seconds),
            }
        )



class MarketSyncAlreadyRunningError(Exception):
    """Raised when a caller attempts to start a second market sync."""

    def __init__(self, job: MarketSyncJobStatus) -> None:
        super().__init__("market sync already running")
        self.job = job


class MarketSyncJobStore:
    """Track market sync jobs and run at most one active job at a time."""

    def __init__(self, sync_fn: MarketSyncFn) -> None:
        self._sync_fn = sync_fn
        self._lock = Lock()
        self._jobs: dict[str, MarketSyncJobStatus] = {}
        self._active_job_id: str | None = None
        self._latest_job_id: str | None = None

    def start(self, background_tasks: BackgroundTasks) -> MarketSyncJobStatus:
        snapshot_time = datetime.now().astimezone()
        job = MarketSyncJobStatus(
            job_id=uuid4().hex,
            status=RunStatus.RUNNING,
            created_at=snapshot_time,
        )

        with self._lock:
            active_job = self._active_job_locked()
            if active_job is not None:
                raise MarketSyncAlreadyRunningError(active_job)
            self._jobs[job.job_id] = job
            self._active_job_id = job.job_id
            self._latest_job_id = job.job_id

        background_tasks.add_task(self._run, job.job_id, snapshot_time)
        return job

    def latest(self) -> MarketSyncJobStatus | None:
        with self._lock:
            if self._latest_job_id is None:
                return None
            job = self._jobs.get(self._latest_job_id)
            return _copy_job(job) if job is not None else None

    def get(self, job_id: str) -> MarketSyncJobStatus | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return _copy_job(job) if job is not None else None

    def _run(self, job_id: str, snapshot_time: datetime) -> None:
        self._update(job_id, started_at=datetime.now().astimezone())

        error: str | None = None
        try:
            result = self._sync_fn(snapshot_time)
            if result.status == RunStatus.FAILED:
                error = "; ".join(result.errors) or "market sync failed"
        except Exception as exc:
            error = str(exc)
            result = SyncResult(
                task="market_bulk_sync",
                status=RunStatus.FAILED,
                expected=0,
                actual=0,
                missing=0,
                snapshot_time=snapshot_time,
                errors=[error],
            )

        self._update(
            job_id,
            status=result.status,
            finished_at=datetime.now().astimezone(),
            result=result,
            error=error,
            clear_active=True,
        )

    def _update(self, job_id: str, *, clear_active: bool = False, **changes: object) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            self._jobs[job_id] = job.model_copy(update=changes)
            if clear_active and self._active_job_id == job_id:
                self._active_job_id = None

    def _active_job_locked(self) -> MarketSyncJobStatus | None:
        if self._active_job_id is None:
            return None
        job = self._jobs.get(self._active_job_id)
        if job is None or job.status != RunStatus.RUNNING:
            self._active_job_id = None
            return None
        return job


def _copy_job(job: MarketSyncJobStatus) -> MarketSyncJobStatus:
    return job.with_runtime_fields().model_copy(deep=True)


def _elapsed_seconds(job: MarketSyncJobStatus) -> int:
    end = job.finished_at or datetime.now().astimezone()
    return max(round((end - job.created_at).total_seconds()), 0)


def _job_message(job: MarketSyncJobStatus, elapsed_seconds: int) -> str:
    if job.status == RunStatus.RUNNING:
        if elapsed_seconds >= 300:
            return "市场同步耗时超过 5 分钟, 请检查上游数据源或后端日志"
        if elapsed_seconds >= 180:
            return "市场同步较慢, 可能是上游数据源响应慢"
        return "正在抓取 AKShare 全市场快照"
    if job.result is not None:
        return (
            f"同步 {job.result.status.value}, 实际 {job.result.actual} / "
            f"预期 {job.result.expected}, 缺失 {job.result.missing}"
        )
    if job.error:
        return job.error
    return f"同步 {job.status.value}"
