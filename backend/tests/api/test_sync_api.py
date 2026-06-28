from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from dataanalysisbase.api import main as api_main
from dataanalysisbase.api.sync_jobs import (
    MarketSyncAlreadyRunningError,
    MarketSyncJobStore,
)
from dataanalysisbase.domain.contracts import MarketSyncJobStatus, SyncResult
from dataanalysisbase.domain.enums import RunStatus
from dataanalysisbase.storage import DuckDBStore, SyncJobRepo


def test_start_market_sync_creates_completed_job(monkeypatch) -> None:
    def fake_run_market_sync(snapshot_time: datetime) -> SyncResult:
        return SyncResult(
            task="market_bulk_sync",
            status=RunStatus.SUCCESS,
            expected=2,
            actual=2,
            missing=0,
            snapshot_time=snapshot_time,
        )

    _patch_job_store(monkeypatch, fake_run_market_sync)
    client = TestClient(api_main.app)

    response = client.post("/api/v1/sync/market")

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "running"
    assert payload["job_id"]

    status_response = client.get(f"/api/v1/sync/market/{payload['job_id']}")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "success"
    assert status_payload["result"]["task"] == "market_bulk_sync"
    assert status_payload["result"]["expected"] == 2
    assert status_payload["result"]["actual"] == 2
    assert status_payload["result"]["missing"] == 0
    assert status_payload["finished_at"] is not None
    assert status_payload["elapsed_seconds"] >= 0
    assert status_payload["message"] == "同步 success, 实际 2 / 预期 2, 缺失 0"


def test_latest_market_sync_returns_latest_job(monkeypatch) -> None:
    def fake_run_market_sync(snapshot_time: datetime) -> SyncResult:
        return SyncResult(
            task="market_bulk_sync",
            status=RunStatus.SUCCESS,
            expected=3,
            actual=3,
            missing=0,
            snapshot_time=snapshot_time,
        )

    _patch_job_store(monkeypatch, fake_run_market_sync)
    client = TestClient(api_main.app)

    start_response = client.post("/api/v1/sync/market")
    job_id = start_response.json()["job_id"]
    latest_response = client.get("/api/v1/sync/market/latest")

    assert latest_response.status_code == 200
    payload = latest_response.json()
    assert payload["job_id"] == job_id
    assert payload["status"] == "success"
    assert payload["result"]["actual"] == 3


def test_latest_market_sync_returns_204_without_job(monkeypatch) -> None:
    _patch_job_store(
        monkeypatch,
        lambda snapshot_time: SyncResult(
            task="market_bulk_sync",
            status=RunStatus.SUCCESS,
            expected=0,
            actual=0,
            missing=0,
            snapshot_time=snapshot_time,
        ),
    )
    client = TestClient(api_main.app)

    response = client.get("/api/v1/sync/market/latest")

    assert response.status_code == 204


def test_market_sync_jobs_returns_recent_jobs(monkeypatch) -> None:
    monkeypatch.setattr(
        api_main,
        "_market_sync_jobs",
        StaticJobStore(
            MarketSyncJobStatus(
                job_id="job-1",
                status=RunStatus.SUCCESS,
                created_at=datetime.fromisoformat("2026-06-28T15:30:00+08:00"),
                finished_at=datetime.fromisoformat("2026-06-28T15:30:12+08:00"),
                result=SyncResult(
                    task="market_bulk_sync",
                    status=RunStatus.SUCCESS,
                    expected=3,
                    actual=3,
                    missing=0,
                    snapshot_time=datetime.fromisoformat("2026-06-28T15:30:00+08:00"),
                ),
                elapsed_seconds=12,
            )
        ),
    )
    client = TestClient(api_main.app)

    response = client.get("/api/v1/sync/market/jobs?limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["job_id"] == "job-1"
    assert payload[0]["result"]["actual"] == 3


def test_start_market_sync_rejects_concurrent_run(monkeypatch) -> None:
    active_job = MarketSyncJobStatus(
        job_id="active-job",
        status=RunStatus.RUNNING,
        created_at=datetime.fromisoformat("2026-06-28T15:30:00+08:00"),
    )
    monkeypatch.setattr(api_main, "_market_sync_jobs", RejectingJobStore(active_job))
    client = TestClient(api_main.app)

    response = client.post("/api/v1/sync/market")

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["message"] == "market sync already running"
    assert detail["job_id"] == "active-job"


def test_get_market_sync_returns_404_for_unknown_job() -> None:
    client = TestClient(api_main.app)

    response = client.get("/api/v1/sync/market/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "market sync job not found"


def test_cancel_market_sync_marks_running_job(monkeypatch) -> None:
    active_job = MarketSyncJobStatus(
        job_id="active-job",
        status=RunStatus.RUNNING,
        created_at=datetime.fromisoformat("2026-06-28T15:30:00+08:00"),
    )
    monkeypatch.setattr(api_main, "_market_sync_jobs", StaticJobStore(active_job))
    client = TestClient(api_main.app)

    response = client.post("/api/v1/sync/market/active-job/cancel")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "running"
    assert payload["cancel_requested"] is True
    assert payload["message"] == "已请求取消, 等待当前 provider 请求结束"


def test_cancel_market_sync_returns_404_for_unknown_job(monkeypatch) -> None:
    monkeypatch.setattr(api_main, "_market_sync_jobs", StaticJobStore(None))
    client = TestClient(api_main.app)

    response = client.post("/api/v1/sync/market/missing/cancel")

    assert response.status_code == 404
    assert response.json()["detail"] == "market sync job not found"


def test_market_sync_job_records_failed_exception(monkeypatch) -> None:
    def fake_run_market_sync(snapshot_time: datetime) -> SyncResult:
        raise RuntimeError("provider timeout")

    _patch_job_store(monkeypatch, fake_run_market_sync)
    client = TestClient(api_main.app)

    response = client.post("/api/v1/sync/market")

    assert response.status_code == 202
    payload = response.json()
    status_response = client.get(f"/api/v1/sync/market/{payload['job_id']}")
    status_payload = status_response.json()
    assert status_payload["status"] == "failed"
    assert status_payload["error"] == "provider timeout"
    assert status_payload["result"]["errors"] == ["provider timeout"]
    assert status_payload["message"] == "同步 failed, 实际 0 / 预期 0, 缺失 0"


def test_market_sync_job_reports_slow_running_message() -> None:
    job = MarketSyncJobStatus(
        job_id="slow-job",
        status=RunStatus.RUNNING,
        created_at=datetime.now().astimezone() - timedelta(seconds=181),
        started_at=datetime.now().astimezone() - timedelta(seconds=180),
    )
    store = MarketSyncJobStore(
        lambda snapshot_time: SyncResult(
            task="market_bulk_sync",
            status=RunStatus.SUCCESS,
            expected=0,
            actual=0,
            missing=0,
            snapshot_time=snapshot_time,
        )
    )
    store._jobs[job.job_id] = job
    store._latest_job_id = job.job_id
    refreshed = store.latest()

    assert refreshed is not None
    assert refreshed.elapsed_seconds >= 180
    assert refreshed.message == "市场同步较慢, 可能是上游数据源响应慢"


def test_market_sync_job_store_restores_latest_persisted_job(tmp_path) -> None:
    db_path = tmp_path / "jobs.duckdb"
    store = DuckDBStore(db_path)
    store.init_schema()
    repo = SyncJobRepo(store)
    created_at = datetime.fromisoformat("2026-06-28T15:30:00+08:00")
    repo.upsert(
        MarketSyncJobStatus(
            job_id="persisted-job",
            status=RunStatus.SUCCESS,
            created_at=created_at,
            finished_at=created_at,
            result=SyncResult(
                task="market_bulk_sync",
                status=RunStatus.SUCCESS,
                expected=1,
                actual=1,
                missing=0,
                snapshot_time=created_at,
            ),
        )
    )
    store.close()

    job_store = MarketSyncJobStore(
        lambda snapshot_time: SyncResult(
            task="market_bulk_sync",
            status=RunStatus.SUCCESS,
            expected=0,
            actual=0,
            missing=0,
            snapshot_time=snapshot_time,
        ),
        job_store_factory=lambda: _sync_job_repo(db_path),
    )

    latest = job_store.latest()
    assert latest is not None
    assert latest.job_id == "persisted-job"
    assert latest.result is not None
    assert latest.result.actual == 1


def test_market_sync_job_store_lists_recent_persisted_jobs(tmp_path) -> None:
    db_path = tmp_path / "jobs.duckdb"
    store = DuckDBStore(db_path)
    store.init_schema()
    repo = SyncJobRepo(store)
    first_at = datetime.fromisoformat("2026-06-28T15:30:00+08:00")
    second_at = datetime.fromisoformat("2026-06-28T15:35:00+08:00")
    repo.upsert(
        MarketSyncJobStatus(
            job_id="job-1",
            status=RunStatus.SUCCESS,
            created_at=first_at,
            finished_at=first_at,
            result=SyncResult(
                task="market_bulk_sync",
                status=RunStatus.SUCCESS,
                expected=1,
                actual=1,
                missing=0,
                snapshot_time=first_at,
            ),
        )
    )
    repo.upsert(
        MarketSyncJobStatus(
            job_id="job-2",
            status=RunStatus.PARTIAL,
            created_at=second_at,
            finished_at=second_at,
            result=SyncResult(
                task="market_bulk_sync",
                status=RunStatus.PARTIAL,
                expected=2,
                actual=1,
                missing=1,
                snapshot_time=second_at,
            ),
        )
    )
    store.close()

    job_store = MarketSyncJobStore(
        lambda snapshot_time: SyncResult(
            task="market_bulk_sync",
            status=RunStatus.SUCCESS,
            expected=0,
            actual=0,
            missing=0,
            snapshot_time=snapshot_time,
        ),
        job_store_factory=lambda: _sync_job_repo(db_path),
    )

    recent = job_store.list_recent(2)

    assert [job.job_id for job in recent] == ["job-2", "job-1"]
    assert recent[0].result is not None
    assert recent[0].result.missing == 1


def _patch_job_store(monkeypatch, sync_fn) -> None:
    monkeypatch.setattr(api_main, "_market_sync_jobs", MarketSyncJobStore(sync_fn))


def _sync_job_repo(db_path) -> SyncJobRepo:
    store = DuckDBStore(db_path)
    store.init_schema()
    return SyncJobRepo(store)


class RejectingJobStore:
    def __init__(self, active_job: MarketSyncJobStatus) -> None:
        self.active_job = active_job

    def start(self, _background_tasks) -> MarketSyncJobStatus:
        raise MarketSyncAlreadyRunningError(self.active_job)


class StaticJobStore:
    def __init__(self, job: MarketSyncJobStatus | None) -> None:
        self.job = job

    def request_cancel(self, _job_id: str) -> MarketSyncJobStatus | None:
        if self.job is None:
            return None
        return self.job.model_copy(
            update={
                "cancel_requested": True,
                "message": "已请求取消, 等待当前 provider 请求结束",
            }
        )

    def list_recent(self, _limit: int) -> list[MarketSyncJobStatus]:
        return [] if self.job is None else [self.job]
