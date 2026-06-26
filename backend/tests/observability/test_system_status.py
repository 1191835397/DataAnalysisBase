from datetime import datetime
from pathlib import Path

from dataanalysisbase.config_loader.settings import Settings
from dataanalysisbase.domain.enums import DataStatus, RunStatus
from dataanalysisbase.observability.provider_connectivity import ProviderConnectivity
from dataanalysisbase.observability.system_status import (
    build_runtime_status,
    has_errors,
    run_doctor,
    validate_config,
)
from dataanalysisbase.storage import DuckDBStore, SnapshotRepo

ROOT_CONFIG = Path(__file__).resolve().parents[3] / "config"


def test_validate_config_accepts_runtime_config() -> None:
    results = validate_config(ROOT_CONFIG)

    assert results
    assert not has_errors(results)


def test_doctor_reports_secret_presence_without_leaking_values(tmp_path: Path) -> None:
    settings = Settings(
        config_dir=ROOT_CONFIG,
        data_dir=tmp_path / "data",
        duckdb_path=tmp_path / "data" / "analytics.duckdb",
        tushare_token="secret-token",
        deepseek_api_key="secret-key",
    )

    results = run_doctor(settings)
    messages = " ".join(result.message for result in results)

    assert "secret-token" not in messages
    assert "secret-key" not in messages
    assert any(
        result.name == "DAB_TUSHARE_TOKEN" and result.message == "configured" for result in results
    )
    assert any(
        result.name == "DAB_DEEPSEEK_API_KEY" and result.message == "configured"
        for result in results
    )
    assert any(result.name == "provider:akshare" for result in results)
    assert not any(result.name.startswith("provider_connectivity:") for result in results)


def test_doctor_can_include_online_provider_connectivity(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings = Settings(
        config_dir=ROOT_CONFIG,
        data_dir=tmp_path / "data",
        duckdb_path=tmp_path / "data" / "analytics.duckdb",
    )
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

    results = run_doctor(settings, include_online=True)

    assert any(
        result.name == "provider_connectivity:akshare" and result.status == "ok"
        for result in results
    )


def test_runtime_status_is_offline_when_database_is_missing(tmp_path: Path) -> None:
    settings = Settings(
        config_dir=ROOT_CONFIG,
        data_dir=tmp_path / "data",
        duckdb_path=tmp_path / "data" / "missing.duckdb",
    )

    status = build_runtime_status(settings)

    assert status.data_status == DataStatus.OFFLINE
    assert status.latest_snapshot_time is None
    assert any(provider.name == "akshare" for provider in status.providers)
    assert status.provider_connectivity == []


def test_runtime_status_can_include_online_provider_connectivity(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings = Settings(
        config_dir=ROOT_CONFIG,
        data_dir=tmp_path / "data",
        duckdb_path=tmp_path / "data" / "missing.duckdb",
    )
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

    status = build_runtime_status(settings, include_online=True)

    assert len(status.provider_connectivity) == 1
    assert status.provider_connectivity[0].name == "akshare"


def test_runtime_status_reports_failed_last_market_run(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "analytics.duckdb"
    store = DuckDBStore(db_path)
    store.init_schema()
    repo = SnapshotRepo(store)
    snapshot_time = datetime(2026, 6, 26, 9, 30)
    repo.begin_run(snapshot_time=snapshot_time, source="akshare", expected=0)
    repo.commit_run(
        snapshot_time=snapshot_time,
        source="akshare",
        status=RunStatus.FAILED,
        actual=0,
        missing=0,
        error="remote disconnected",
    )
    store.close()
    settings = Settings(config_dir=ROOT_CONFIG, data_dir=tmp_path / "data", duckdb_path=db_path)

    status = build_runtime_status(settings)

    assert status.data_status == DataStatus.FAILED
    assert status.last_market_run is not None
    assert status.last_market_run.status == "failed"
    assert status.last_market_run.error == "remote disconnected"
