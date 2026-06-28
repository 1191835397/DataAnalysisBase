from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from dataanalysisbase.api.main import app
from dataanalysisbase.config_loader.settings import Settings
from dataanalysisbase.domain.contracts import MarketRow
from dataanalysisbase.ingest import MarketBulkSync
from dataanalysisbase.providers import MarketSnapshotBatch
from dataanalysisbase.storage import AggregateRepo, DuckDBStore, SnapshotRepo

ROOT_CONFIG = Path(__file__).resolve().parents[3] / "config"


def test_market_overview_endpoint_returns_latest_aggregate(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db_path = _seed_market_data(tmp_path)
    _patch_settings(monkeypatch, db_path)
    client = TestClient(app)

    response = client.get("/api/v1/market/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["stock_count"] == 2
    assert payload["up_count"] == 1
    assert payload["down_count"] == 1
    assert payload["source"] == "mock"


def test_stocks_endpoint_returns_filtered_page(monkeypatch, tmp_path: Path) -> None:
    db_path = _seed_market_data(tmp_path)
    _patch_settings(monkeypatch, db_path)
    client = TestClient(app)

    response = client.get("/api/v1/stocks?filter=gainers&size=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["page"] == 1
    assert payload["size"] == 1
    assert payload["items"][0]["security_id"] == "600519.SH"
    assert payload["items"][0]["change_pct"] == 1.5


def test_industries_endpoint_returns_latest_aggregates(monkeypatch, tmp_path: Path) -> None:
    db_path = _seed_market_data(tmp_path)
    _patch_settings(monkeypatch, db_path)
    client = TestClient(app)

    response = client.get("/api/v1/industries?limit=1")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["industry_code"] == "TEST"
    assert payload[0]["stock_count"] == 2


def test_industry_stocks_endpoint_returns_filtered_page(monkeypatch, tmp_path: Path) -> None:
    db_path = _seed_market_data(tmp_path)
    _patch_settings(monkeypatch, db_path)
    client = TestClient(app)

    response = client.get("/api/v1/industries/TEST/stocks?size=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert len(payload["items"]) == 1
    assert payload["items"][0]["industry_code"] == "TEST"


def test_unknown_industry_stocks_endpoint_matches_null_industry(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db_path = _seed_market_data(tmp_path, include_unknown_industry=True)
    _patch_settings(monkeypatch, db_path)
    client = TestClient(app)

    response = client.get("/api/v1/industries/UNKNOWN/stocks?size=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["security_id"] == "000001.SZ"
    assert payload["items"][0]["industry_code"] is None


def test_market_data_endpoint_reports_unavailable_database(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _patch_settings(monkeypatch, tmp_path / "missing.duckdb")
    client = TestClient(app)

    response = client.get("/api/v1/stocks")

    assert response.status_code == 503
    assert "market data is not available" in response.json()["detail"]


def test_stocks_endpoint_rejects_invalid_page_size() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/stocks?size=201")

    assert response.status_code == 422


def test_industries_endpoint_rejects_invalid_limit() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/industries?limit=201")

    assert response.status_code == 422


def test_industry_stocks_endpoint_rejects_invalid_page_size() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/industries/TEST/stocks?size=201")

    assert response.status_code == 422


def test_market_alerts_endpoint_returns_system_and_stock_alerts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db_path = _seed_market_data(tmp_path, include_alert_rows=True)
    _patch_settings(monkeypatch, db_path)
    client = TestClient(app)

    response = client.get("/api/v1/alerts/market?limit=20")

    assert response.status_code == 200
    payload = response.json()
    kinds = {alert["kind"] for alert in payload}
    assert "data_stale" in kinds
    assert "limit_up" in kinds
    assert "limit_down" in kinds
    assert "volume_surge" in kinds
    assert any(alert["security_id"] == "688001.SH" for alert in payload)


def test_market_alert_groups_endpoint_deduplicates_security_alerts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db_path = _seed_market_data(tmp_path, include_alert_rows=True)
    _patch_settings(monkeypatch, db_path)
    client = TestClient(app)

    response = client.get("/api/v1/alerts/market/groups?limit=20")

    assert response.status_code == 200
    payload = response.json()
    security_group = next(
        group for group in payload if group["security_id"] == "688001.SH"
    )
    assert security_group["severity"] == "high"
    assert set(security_group["kinds"]) >= {"limit_up", "volume_surge", "extreme_move"}
    assert security_group["alert_count"] == len(security_group["alerts"])


def test_market_alerts_endpoint_returns_offline_alert_without_snapshot(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "missing.duckdb"
    _patch_settings(monkeypatch, db_path)
    client = TestClient(app)

    response = client.get("/api/v1/alerts/market")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["kind"] == "offline"
    assert payload[0]["severity"] == "high"


class MockProvider:
    name = "mock"

    def __init__(self, rows: list[MarketRow]) -> None:
        self.rows = rows

    def fetch_market_snapshot(self, snapshot_time: datetime) -> MarketSnapshotBatch:
        return MarketSnapshotBatch(
            snapshot_time=snapshot_time,
            source=self.name,
            expected=len(self.rows),
            rows=self.rows,
        )


def _seed_market_data(
    tmp_path: Path,
    *,
    include_unknown_industry: bool = False,
    include_alert_rows: bool = False,
) -> Path:
    db_path = tmp_path / "analytics.duckdb"
    store = DuckDBStore(db_path)
    store.init_schema()
    snapshot_time = datetime(2026, 6, 26, 10, 56, tzinfo=ZoneInfo("Asia/Shanghai"))
    sync = MarketBulkSync(
        MockProvider(
            [
                _row(snapshot_time, "600519.SH", "贵州茅台", 1.5, industry_code="TEST"),
                _row(snapshot_time, "300750.SZ", "宁德时代", -2.0, industry_code="TEST"),
                *(
                    [
                        _row(
                            snapshot_time,
                            "688001.SH",
                            "华兴源创",
                            10.2,
                            industry_code="ALERT",
                            volume_ratio=3.1,
                        ),
                        _row(
                            snapshot_time,
                            "000002.SZ",
                            "万科A",
                            -10.1,
                            industry_code="ALERT",
                        ),
                    ]
                    if include_alert_rows
                    else []
                ),
                *(
                    [_row(snapshot_time, "000001.SZ", "平安银行", 0.1, industry_code=None)]
                    if include_unknown_industry
                    else []
                ),
            ]
        ),
        SnapshotRepo(store),
        AggregateRepo(store),
    )
    sync.run_once(snapshot_time)
    store.close()
    return db_path


def _row(
    snapshot_time: datetime,
    security_id: str,
    name: str,
    change_pct: float,
    *,
    industry_code: str | None,
    volume_ratio: float = 1.5,
) -> MarketRow:
    return MarketRow(
        snapshot_time=snapshot_time,
        security_id=security_id,
        name=name,
        source="mock",
        fetched_at=snapshot_time,
        price=100.0,
        change_pct=change_pct,
        volume=1000,
        amount=100000,
        turnover_rate=0.5,
        volume_ratio=volume_ratio,
        pe_ttm=20,
        pb=3,
        market_cap=1000000,
        industry_code=industry_code,
    )


def _patch_settings(monkeypatch, duckdb_path: Path) -> None:
    settings = Settings(
        config_dir=ROOT_CONFIG,
        data_dir=duckdb_path.parent,
        duckdb_path=duckdb_path,
    )
    monkeypatch.setattr("dataanalysisbase.api.market_data.load_settings", lambda: settings)
    monkeypatch.setattr("dataanalysisbase.api.market_alerts.load_settings", lambda: settings)
