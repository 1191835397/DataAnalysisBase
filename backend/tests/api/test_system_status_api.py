from fastapi.testclient import TestClient

from dataanalysisbase.api.main import app
from dataanalysisbase.observability.provider_connectivity import ProviderConnectivity


def test_system_status_endpoint_returns_runtime_status() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/system/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "dataanalysisbase"
    assert "data_status" in payload
    assert "generated_at" in payload
    assert "providers" in payload
    assert payload["provider_connectivity"] == []
    assert "last_market_run" in payload


def test_system_status_endpoint_can_include_online_connectivity(monkeypatch) -> None:
    monkeypatch.setattr(
        "dataanalysisbase.observability.system_status.build_provider_connectivity",
        lambda _providers: [
            ProviderConnectivity(
                name="akshare",
                status="ok",
                enabled=True,
                endpoint="https://www.eastmoney.com/",
                message="HTTP 200 in 12 ms",
                elapsed_ms=12.0,
            )
        ],
    )
    client = TestClient(app)

    response = client.get("/api/v1/system/status?online=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider_connectivity"][0]["name"] == "akshare"
