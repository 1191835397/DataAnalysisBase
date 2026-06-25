from pathlib import Path

from dataanalysisbase.config_loader.settings import Settings
from dataanalysisbase.domain.enums import DataStatus
from dataanalysisbase.observability.system_status import (
    build_runtime_status,
    has_errors,
    run_doctor,
    validate_config,
)

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
