from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from dataanalysisbase.api import main as api_main
from dataanalysisbase.domain.contracts import SyncResult
from dataanalysisbase.domain.enums import RunStatus


def test_sync_market_endpoint_runs_market_sync(monkeypatch) -> None:
    def fake_run_market_sync(snapshot_time: datetime) -> SyncResult:
        return SyncResult(
            task="market_bulk_sync",
            status=RunStatus.SUCCESS,
            expected=2,
            actual=2,
            missing=0,
            snapshot_time=snapshot_time,
        )

    monkeypatch.setattr(api_main, "run_market_sync", fake_run_market_sync)
    client = TestClient(api_main.app)

    response = client.post("/api/v1/sync/market")

    assert response.status_code == 200
    payload = response.json()
    assert payload["task"] == "market_bulk_sync"
    assert payload["status"] == "success"
    assert payload["expected"] == 2
    assert payload["actual"] == 2
    assert payload["missing"] == 0
    assert payload["snapshot_time"] is not None


def test_sync_market_endpoint_rejects_concurrent_run() -> None:
    api_main._market_sync_lock.acquire()
    try:
        client = TestClient(api_main.app)

        response = client.post("/api/v1/sync/market")
    finally:
        api_main._market_sync_lock.release()

    assert response.status_code == 409
    assert response.json()["detail"] == "market sync already running"
