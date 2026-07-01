from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from dataanalysisbase.api.main import app
from dataanalysisbase.api.market_alerts import _refresh_persisted_alerts
from dataanalysisbase.config_loader.settings import Settings
from dataanalysisbase.domain.contracts import MarketRow
from dataanalysisbase.domain.enums import AlertStatus
from dataanalysisbase.ingest import MarketBulkSync
from dataanalysisbase.providers import MarketSnapshotBatch
from dataanalysisbase.storage import (
    AggregateRepo,
    AlertRepo,
    DuckDBStore,
    SnapshotRepo,
)

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


def test_stock_detail_endpoint_returns_snapshot_and_alert_history(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db_path = _seed_market_data(tmp_path, include_alert_rows=True)
    _patch_settings(monkeypatch, db_path)
    client = TestClient(app)

    response = client.get("/api/v1/stocks/000004.SZ?alert_limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot"]["security_id"] == "000004.SZ"
    assert payload["snapshot"]["industry_code"] == "ALERT"
    assert payload["snapshot"]["change_pct"] == 10.2
    assert payload["snapshot"]["is_suspended"] is False
    assert {alert["kind"] for alert in payload["alerts"]} >= {
        "limit_up",
        "volume_surge",
        "extreme_move",
    }


def test_stock_detail_endpoint_returns_404_for_missing_stock(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db_path = _seed_market_data(tmp_path)
    _patch_settings(monkeypatch, db_path)
    client = TestClient(app)

    response = client.get("/api/v1/stocks/999999.SH")

    assert response.status_code == 404
    assert response.json()["detail"] == "stock not found in latest snapshot"


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
    assert any(alert["security_id"] == "000004.SZ" for alert in payload)


def test_market_alerts_endpoint_skips_delta_alert_without_previous_snapshot(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db_path = _seed_market_data(
        tmp_path,
        include_alert_rows=True,
        include_previous_snapshot=False,
    )
    _patch_settings(monkeypatch, db_path)
    client = TestClient(app)

    response = client.get("/api/v1/alerts/market?limit=20")

    assert response.status_code == 200
    stock_alerts = [
        alert for alert in response.json() if alert["security_id"] == "000004.SZ"
    ]
    assert "limit_up" in {alert["kind"] for alert in stock_alerts}
    assert "extreme_move" not in {alert["kind"] for alert in stock_alerts}


def test_market_alerts_endpoint_skips_untradable_stock_alerts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db_path = _seed_market_data(tmp_path, include_untradable_alert_row=True)
    _patch_settings(monkeypatch, db_path)
    client = TestClient(app)

    response = client.get("/api/v1/alerts/market?limit=20")

    assert response.status_code == 200
    assert not [
        alert for alert in response.json() if alert["security_id"] == "000003.SZ"
    ]


def test_market_alerts_endpoint_uses_board_specific_limit_thresholds(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db_path = _seed_market_data(tmp_path, include_board_limit_rows=True)
    _patch_settings(monkeypatch, db_path)
    client = TestClient(app)

    response = client.get("/api/v1/alerts/market?limit=50")

    assert response.status_code == 200
    limit_up_alerts = {
        alert["security_id"]: alert
        for alert in response.json()
        if alert["kind"] == "limit_up"
    }
    assert set(limit_up_alerts) == {
        "600000.SH",
        "600520.SH",
        "688001.SH",
        "830001.BJ",
    }
    assert limit_up_alerts["600000.SH"]["threshold"] == 4.9
    assert limit_up_alerts["688001.SH"]["threshold"] == 19.9
    assert limit_up_alerts["830001.BJ"]["threshold"] == 29.9


def test_market_alerts_endpoint_skips_new_listing_limit_alerts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db_path = _seed_market_data(tmp_path, include_new_listing_rows=True)
    _patch_settings(monkeypatch, db_path)
    client = TestClient(app)

    response = client.get("/api/v1/alerts/market?limit=50")

    assert response.status_code == 200
    limit_up_security_ids = {
        alert["security_id"] for alert in response.json() if alert["kind"] == "limit_up"
    }
    assert "001001.SZ" not in limit_up_security_ids
    assert "001002.SZ" in limit_up_security_ids


def test_market_alerts_endpoint_skips_ex_dividend_delta_alerts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db_path = _seed_market_data(tmp_path, include_ex_dividend_alert_row=True)
    _patch_settings(monkeypatch, db_path)
    client = TestClient(app)

    response = client.get("/api/v1/alerts/market?limit=20")

    assert response.status_code == 200
    ex_dividend_alerts = [
        alert for alert in response.json() if alert["security_id"] == "600520.SH"
    ]
    assert ex_dividend_alerts == []


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
        group for group in payload if group["security_id"] == "000004.SZ"
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


def test_market_alert_status_update_persists_across_refresh(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db_path = _seed_market_data(tmp_path, include_alert_rows=True)
    _patch_settings(monkeypatch, db_path)
    client = TestClient(app)

    alerts_response = client.get("/api/v1/alerts/market?limit=20")
    alert_id = next(
        alert["alert_id"]
        for alert in alerts_response.json()
        if alert["kind"] == "data_stale"
    )

    update_response = client.patch(
        f"/api/v1/alerts/market/{alert_id}",
        json={"status": "handled"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "handled"

    refreshed_response = client.get("/api/v1/alerts/market?limit=20")
    refreshed_alert = next(
        alert for alert in refreshed_response.json() if alert["alert_id"] == alert_id
    )
    assert refreshed_alert["status"] == "handled"
    assert refreshed_alert["trigger_count"] == 1


def test_market_alert_status_update_returns_404_for_missing_alert(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db_path = _seed_market_data(tmp_path)
    _patch_settings(monkeypatch, db_path)
    client = TestClient(app)

    response = client.patch(
        "/api/v1/alerts/market/missing-alert",
        json={"status": "read"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "market alert not found"


def test_market_alert_refresh_respects_cooldown_window(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db_path = _seed_market_data(tmp_path, include_alert_rows=True)
    config_dir = _write_surveillance_rules(
        tmp_path,
        dedupe_minutes=30,
        limit_up_cooldown_minutes=30,
    )
    settings = Settings(
        config_dir=config_dir,
        data_dir=db_path.parent,
        duckdb_path=db_path,
    )
    monkeypatch.setattr("dataanalysisbase.api.market_alerts.load_settings", lambda: settings)
    alert_id = "limit_up:000004.SZ"

    _refresh_persisted_alerts(db_path, config_dir)
    repo, store = _alert_repo(db_path)
    repo.update_status(alert_id, AlertStatus.HANDLED)
    first = repo.get(alert_id)
    assert first is not None
    store.close()

    _append_alert_snapshot(
        db_path,
        datetime(2026, 6, 26, 11, 10, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    _refresh_persisted_alerts(db_path, config_dir)

    repo, store = _alert_repo(db_path, read_only=True)
    within_window = repo.get(alert_id)
    assert within_window is not None
    assert within_window.status == AlertStatus.HANDLED
    assert within_window.trigger_count == 1
    assert within_window.last_triggered_at == first.last_triggered_at
    store.close()

    _append_alert_snapshot(
        db_path,
        datetime(2026, 6, 26, 11, 40, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    _refresh_persisted_alerts(db_path, config_dir)

    repo, store = _alert_repo(db_path, read_only=True)
    after_window = repo.get(alert_id)
    assert after_window is not None
    assert after_window.status == AlertStatus.NEW
    assert after_window.trigger_count == 2
    assert after_window.last_triggered_at.isoformat() == "2026-06-26T11:40:00+08:00"
    store.close()


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
    include_previous_snapshot: bool = True,
    include_untradable_alert_row: bool = False,
    include_board_limit_rows: bool = False,
    include_new_listing_rows: bool = False,
    include_ex_dividend_alert_row: bool = False,
) -> Path:
    db_path = tmp_path / "analytics.duckdb"
    store = DuckDBStore(db_path)
    store.init_schema()
    snapshot_time = datetime(2026, 6, 26, 10, 56, tzinfo=ZoneInfo("Asia/Shanghai"))
    if include_alert_rows and include_previous_snapshot:
        _sync_rows(
            store,
            snapshot_time - timedelta(minutes=30),
            [
                _row(
                    snapshot_time - timedelta(minutes=30),
                    "000004.SZ",
                    "华兴源创",
                    1.0,
                    industry_code="ALERT",
                    price=95.0,
                )
            ],
        )
    if include_ex_dividend_alert_row:
        _sync_rows(
            store,
            snapshot_time - timedelta(minutes=30),
            [
                _row(
                    snapshot_time - timedelta(minutes=30),
                    "600520.SH",
                    "除权测试",
                    1.0,
                    industry_code="TEST",
                    price=100.0,
                )
            ],
        )
    _sync_rows(
        store,
        snapshot_time,
        [
            _row(snapshot_time, "600519.SH", "贵州茅台", 1.5, industry_code="TEST"),
            _row(snapshot_time, "300750.SZ", "宁德时代", -2.0, industry_code="TEST"),
            *(
                [
                    _row(
                        snapshot_time,
                        "000004.SZ",
                        "华兴源创",
                        10.2,
                        industry_code="ALERT",
                        price=100.0,
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
            *(
                [
                    _row(
                        snapshot_time,
                        "000003.SZ",
                        "停牌测试",
                        10.5,
                        industry_code="ALERT",
                        is_suspended=True,
                        volume_ratio=3.5,
                    )
                ]
                if include_untradable_alert_row
                else []
            ),
            *(
                _board_limit_rows(snapshot_time) if include_board_limit_rows else []
            ),
            *(
                _new_listing_rows(snapshot_time) if include_new_listing_rows else []
            ),
            *(
                [
                    _row(
                        snapshot_time,
                        "600520.SH",
                        "除权测试",
                        1.0,
                        industry_code="TEST",
                        price=80.0,
                        ex_dividend=True,
                    )
                ]
                if include_ex_dividend_alert_row
                else []
            ),
        ],
    )
    store.close()
    return db_path


def _sync_rows(store: DuckDBStore, snapshot_time: datetime, rows: list[MarketRow]) -> None:
    sync = MarketBulkSync(
        MockProvider(rows),
        SnapshotRepo(store),
        AggregateRepo(store),
    )
    sync.run_once(snapshot_time)


def _board_limit_rows(snapshot_time: datetime) -> list[MarketRow]:
    return [
        _row(snapshot_time, "600520.SH", "主板达标", 9.9, industry_code="LIMIT"),
        _row(snapshot_time, "600000.SH", "ST浦发", 5.1, industry_code="LIMIT"),
        _row(snapshot_time, "600001.SH", "ST未达", 4.8, industry_code="LIMIT"),
        _row(snapshot_time, "688001.SH", "华兴源创", 19.9, industry_code="LIMIT"),
        _row(snapshot_time, "300001.SZ", "创业未达", 10.0, industry_code="LIMIT"),
        _row(snapshot_time, "300002.SZ", "创业接近", 19.8, industry_code="LIMIT"),
        _row(snapshot_time, "830001.BJ", "北交达标", 29.9, industry_code="LIMIT"),
        _row(snapshot_time, "830002.BJ", "北交未达", 20.0, industry_code="LIMIT"),
    ]


def _new_listing_rows(snapshot_time: datetime) -> list[MarketRow]:
    return [
        _row(
            snapshot_time,
            "001001.SZ",
            "新股首日",
            30.0,
            industry_code="NEW",
            listing_date=date(2026, 6, 23),
        ),
        _row(
            snapshot_time,
            "001002.SZ",
            "老股达标",
            9.9,
            industry_code="NEW",
            listing_date=date(2026, 6, 1),
        ),
    ]


def _row(
    snapshot_time: datetime,
    security_id: str,
    name: str,
    change_pct: float,
    *,
    industry_code: str | None,
    price: float = 100.0,
    volume: float = 1000,
    amount: float = 100000,
    volume_ratio: float = 1.5,
    listing_date: date | None = None,
    ex_dividend: bool = False,
    is_suspended: bool = False,
) -> MarketRow:
    return MarketRow(
        snapshot_time=snapshot_time,
        security_id=security_id,
        name=name,
        source="mock",
        fetched_at=snapshot_time,
        price=price,
        change_pct=change_pct,
        volume=volume,
        amount=amount,
        turnover_rate=0.5,
        volume_ratio=volume_ratio,
        pe_ttm=20,
        pb=3,
        market_cap=1000000,
        industry_code=industry_code,
        listing_date=listing_date,
        ex_dividend=ex_dividend,
        is_suspended=is_suspended,
    )


def _patch_settings(monkeypatch, duckdb_path: Path) -> None:
    settings = Settings(
        config_dir=ROOT_CONFIG,
        data_dir=duckdb_path.parent,
        duckdb_path=duckdb_path,
    )
    monkeypatch.setattr("dataanalysisbase.api.market_data.load_settings", lambda: settings)
    monkeypatch.setattr("dataanalysisbase.api.market_alerts.load_settings", lambda: settings)


def _append_alert_snapshot(db_path: Path, snapshot_time: datetime) -> None:
    store = DuckDBStore(db_path)
    sync = MarketBulkSync(
        MockProvider(
            [
                _row(
                    snapshot_time,
                    "000004.SZ",
                    "华兴源创",
                    10.4,
                    industry_code="ALERT",
                    volume_ratio=3.3,
                )
            ]
        ),
        SnapshotRepo(store),
        AggregateRepo(store),
    )
    sync.run_once(snapshot_time)
    store.close()


def _alert_repo(db_path: Path, *, read_only: bool = False) -> tuple[AlertRepo, DuckDBStore]:
    store = DuckDBStore(db_path, read_only=read_only)
    return AlertRepo(store), store


def _write_surveillance_rules(
    tmp_path: Path,
    *,
    dedupe_minutes: int,
    limit_up_cooldown_minutes: int,
) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "surveillance_rules.yaml").write_text(
        f"""
version: "1.0"
dedupe:
  window_minutes: {dedupe_minutes}
rules:
  limit_up:
    scope: market
    severity: high
    condition: {{ field: change_pct, op: gte, value: 9.9 }}
    enabled: true
    cooldown_minutes: {limit_up_cooldown_minutes}
  limit_down:
    scope: market
    severity: high
    condition: {{ field: change_pct, op: lte, value: -9.9 }}
    enabled: true
  price_spike:
    scope: market
    severity: medium
    condition: {{ field: delta_price_pct, op: gte, value: 3.0 }}
    enabled: true
  volume_surge:
    scope: market
    severity: medium
    condition: {{ field: volume_ratio, op: gte, value: 2.0 }}
    enabled: true
""".lstrip(),
        encoding="utf-8",
    )
    return config_dir
