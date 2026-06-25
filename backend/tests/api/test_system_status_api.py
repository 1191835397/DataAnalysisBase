from fastapi.testclient import TestClient

from dataanalysisbase.api.main import app


def test_system_status_endpoint_returns_runtime_status() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/system/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "dataanalysisbase"
    assert "data_status" in payload
    assert "generated_at" in payload
    assert "providers" in payload
