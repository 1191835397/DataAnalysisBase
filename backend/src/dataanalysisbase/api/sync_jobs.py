"""In-process sync job tracking for API-triggered operations."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from threading import Lock
from uuid import uuid4

from fastapi import BackgroundTasks

from dataanalysisbase.domain.contracts import MarketSyncJobStatus, SyncResult
from dataanalysisbase.domain.enums import RunStatus
from dataanalysisbase.storage import DuckDBStore, SyncJobRepo

MarketSyncFn = Callable[[datetime], SyncResult]
JobStoreFactory = Callable[[], SyncJobRepo]


class MarketSyncAlreadyRunningError(Exception):
    """Raised when a caller attempts to start a second market sync."""

    def __init__(self, job: MarketSyncJobStatus) -> None:
        super().__init__("market sync already running")
        self.job = job


class MarketSyncJobStore:
    """Track market sync jobs and run at most one active job at a time."""

    def __init__(
        self,
        sync_fn: MarketSyncFn,
        *,
        job_store_factory: JobStoreFactory | None = None,
    ) -> None:
        self._sync_fn = sync_fn
        self._job_store_factory = job_store_factory
        self._lock = Lock()
        self._jobs: dict[str, MarketSyncJobStatus] = {}
        self._active_job_id: str | None = None
        self._latest_job_id: str | None = None
        self._restored = job_store_factory is None

    def start(self, background_tasks: BackgroundTasks) -> MarketSyncJobStatus:
        self._ensure_restored()
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
            self._persist_locked(job)

        background_tasks.add_task(self._run, job.job_id, snapshot_time)
        return job

    def latest(self) -> MarketSyncJobStatus | None:
        self._ensure_restored()
        with self._lock:
            if self._latest_job_id is None:
                return None
            job = self._jobs.get(self._latest_job_id)
            return _copy_job(job) if job is not None else None

    def get(self, job_id: str) -> MarketSyncJobStatus | None:
        self._ensure_restored()
        with self._lock:
            job = self._jobs.get(job_id)
            return _copy_job(job) if job is not None else None

    def request_cancel(self, job_id: str) -> MarketSyncJobStatus | None:
        self._ensure_restored()
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job.status == RunStatus.RUNNING:
                job = job.model_copy(
                    update={
                        "cancel_requested": True,
                        "message": "已请求取消, 等待当前 provider 请求结束",
                    }
                )
                self._jobs[job_id] = job
                self._persist_locked(job)
            return _copy_job(job)

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

        with self._lock:
            job = self._jobs.get(job_id)
            cancel_requested = job.cancel_requested if job is not None else False

        if cancel_requested and result.status != RunStatus.FAILED:
            error = "market sync was cancelled by user"
            result = result.model_copy(
                update={
                    "status": RunStatus.FAILED,
                    "errors": [*result.errors, error],
                }
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
            updated_job = job.model_copy(update=changes)
            self._jobs[job_id] = updated_job
            self._persist_locked(updated_job)
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

    def _ensure_restored(self) -> None:
        if self._restored:
            return
        with self._lock:
            if self._restored:
                return
            latest_job = self._load_latest_persisted_job()
            if latest_job is not None:
                self._jobs[latest_job.job_id] = latest_job
                self._latest_job_id = latest_job.job_id
            self._restored = True

    def _load_latest_persisted_job(self) -> MarketSyncJobStatus | None:
        repo, store = self._open_job_repo()
        try:
            repo.mark_interrupted_running()
            return repo.latest()
        finally:
            store.close()

    def _persist_locked(self, job: MarketSyncJobStatus) -> None:
        if self._job_store_factory is None:
            return
        repo, store = self._open_job_repo()
        try:
            repo.upsert(_with_runtime_fields(job))
        finally:
            store.close()

    def _open_job_repo(self) -> tuple[SyncJobRepo, DuckDBStore]:
        repo = self._job_store_factory
        if repo is None:
            raise RuntimeError("job store factory is not configured")
        sync_job_repo = repo()
        return sync_job_repo, sync_job_repo.store


def _copy_job(job: MarketSyncJobStatus) -> MarketSyncJobStatus:
    return _with_runtime_fields(job).model_copy(deep=True)


def _with_runtime_fields(job: MarketSyncJobStatus) -> MarketSyncJobStatus:
    elapsed_seconds = _elapsed_seconds(job)
    return job.model_copy(
        update={
            "elapsed_seconds": elapsed_seconds,
            "message": _job_message(job, elapsed_seconds),
        }
    )


def _elapsed_seconds(job: MarketSyncJobStatus) -> int:
    end = job.finished_at or datetime.now().astimezone()
    return max(round((end - job.created_at).total_seconds()), 0)


def _job_message(job: MarketSyncJobStatus, elapsed_seconds: int) -> str:
    if job.cancel_requested and job.status == RunStatus.RUNNING:
        return "已请求取消, 等待当前 provider 请求结束"
    if job.cancel_requested:
        return "同步已取消"
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
