"""System status and local diagnostics helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from dataanalysisbase.common.errors import ConfigError, StorageError
from dataanalysisbase.config_loader.loader import (
    load_fusion_policy,
    load_providers,
    load_reconcile_thresholds,
    load_settings,
    load_surveillance_rules,
    load_sync_schedule,
    load_watchlist,
)
from dataanalysisbase.config_loader.settings import Settings
from dataanalysisbase.domain.enums import DataStatus
from dataanalysisbase.observability.provider_connectivity import (
    ProviderConnectivity,
    build_provider_connectivity,
)
from dataanalysisbase.observability.provider_health import (
    ProviderHealth,
    build_provider_health,
    provider_config_error,
)
from dataanalysisbase.storage import DuckDBStore, SnapshotRepo

CONFIG_LOADERS = {
    "providers.yaml": load_providers,
    "sync_schedule.yaml": load_sync_schedule,
    "surveillance_rules.yaml": load_surveillance_rules,
    "watchlist.yaml": load_watchlist,
    "fusion_policy.yaml": load_fusion_policy,
    "reconcile_thresholds.yaml": load_reconcile_thresholds,
}


class CheckResult(BaseModel):
    """Single diagnostic check result."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: Literal["ok", "warning", "error"]
    message: str


class MarketRunStatus(BaseModel):
    """Latest whole-market snapshot run status."""

    model_config = ConfigDict(frozen=True)

    snapshot_time: datetime
    source: str
    status: str
    expected: int
    actual: int
    missing: int
    error: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class RuntimeStatus(BaseModel):
    """Current local runtime status for CLI and API consumers."""

    model_config = ConfigDict(frozen=True)

    service: str = "dataanalysisbase"
    generated_at: datetime
    run_mode: str
    data_status: DataStatus
    latest_snapshot_time: datetime | None = None
    duckdb_path: str
    config_dir: str
    providers: list[ProviderHealth]
    provider_connectivity: list[ProviderConnectivity] = Field(default_factory=list)
    last_market_run: MarketRunStatus | None = None


def validate_config(config_dir: Path | None = None) -> list[CheckResult]:
    """Load every runtime config file and return validation results."""

    settings = load_settings()
    resolved_config_dir = config_dir or settings.config_dir
    results: list[CheckResult] = []
    for filename, loader in CONFIG_LOADERS.items():
        try:
            loader(resolved_config_dir)
        except ConfigError as exc:
            results.append(
                CheckResult(name=filename, status="error", message=_single_line(str(exc)))
            )
        else:
            results.append(CheckResult(name=filename, status="ok", message="valid"))
    return results


def run_doctor(
    settings: Settings | None = None,
    *,
    include_online: bool = False,
) -> list[CheckResult]:
    """Run diagnostics, with online provider probes only when explicitly requested."""

    settings = settings or load_settings()
    results: list[CheckResult] = []
    results.append(_path_check("config_dir", settings.config_dir, should_exist=True))
    results.append(_path_check("data_dir", settings.data_dir, should_exist=False))
    results.append(_parent_path_check("duckdb_parent", settings.duckdb_path.parent))
    results.extend(validate_config(settings.config_dir))
    results.append(_secret_presence_check("DAB_TUSHARE_TOKEN", settings.tushare_token))
    results.append(_secret_presence_check("DAB_DEEPSEEK_API_KEY", settings.deepseek_api_key))
    results.extend(_provider_checks(settings.config_dir))
    if include_online:
        results.extend(_provider_connectivity_checks(settings.config_dir))
    results.append(_duckdb_check(settings.duckdb_path))
    return results


def build_runtime_status(
    settings: Settings | None = None,
    *,
    include_online: bool = False,
) -> RuntimeStatus:
    """Build a compact system status snapshot without mutating runtime state."""

    settings = settings or load_settings()
    snapshot_state = _snapshot_state(settings.duckdb_path)
    latest_snapshot_time = snapshot_state.latest_snapshot_time
    providers = _provider_health(settings.config_dir)
    provider_connectivity = _provider_connectivity(settings.config_dir) if include_online else []
    return RuntimeStatus(
        generated_at=datetime.now(UTC),
        run_mode=settings.run_mode,
        data_status=_data_status(latest_snapshot_time, snapshot_state.last_market_run),
        latest_snapshot_time=latest_snapshot_time,
        duckdb_path=str(settings.duckdb_path),
        config_dir=str(settings.config_dir),
        providers=providers,
        provider_connectivity=provider_connectivity,
        last_market_run=snapshot_state.last_market_run,
    )


def has_errors(results: list[CheckResult]) -> bool:
    """Return true if any diagnostic result failed."""

    return any(result.status == "error" for result in results)


def _path_check(name: str, path: Path, *, should_exist: bool) -> CheckResult:
    if path.exists():
        return CheckResult(name=name, status="ok", message=str(path))
    if should_exist:
        return CheckResult(name=name, status="error", message=f"not found: {path}")
    return CheckResult(name=name, status="warning", message=f"not created yet: {path}")


def _parent_path_check(name: str, path: Path) -> CheckResult:
    if path.exists():
        return CheckResult(name=name, status="ok", message=str(path))
    return CheckResult(
        name=name,
        status="warning",
        message=f"will be created on first write: {path}",
    )


def _secret_presence_check(name: str, value: str | None) -> CheckResult:
    if value:
        return CheckResult(name=name, status="ok", message="configured")
    return CheckResult(name=name, status="warning", message="not configured")


def _duckdb_check(path: Path) -> CheckResult:
    if not path.exists():
        return CheckResult(name="duckdb", status="warning", message=f"not created yet: {path}")

    try:
        store = DuckDBStore(path, read_only=True)
        store.connect()
        store.close()
    except StorageError as exc:
        return CheckResult(name="duckdb", status="error", message=_single_line(str(exc)))
    return CheckResult(name="duckdb", status="ok", message=str(path))


def _provider_checks(config_dir: Path) -> list[CheckResult]:
    try:
        providers = _provider_health(config_dir)
    except ConfigError as exc:
        return [CheckResult(name="provider_health", status="error", message=_single_line(str(exc)))]
    return [
        CheckResult(
            name=f"provider:{provider.name}",
            status=provider.status,
            message=provider.message,
        )
        for provider in providers
        if provider.enabled
    ]


def _provider_connectivity_checks(config_dir: Path) -> list[CheckResult]:
    try:
        connectivity = _provider_connectivity(config_dir)
    except ConfigError as exc:
        return [
            CheckResult(
                name="provider_connectivity",
                status="error",
                message=_single_line(str(exc)),
            )
        ]
    return [
        CheckResult(
            name=f"provider_connectivity:{provider.name}",
            status=provider.status,
            message=provider.message,
        )
        for provider in connectivity
    ]


def _provider_health(config_dir: Path) -> list[ProviderHealth]:
    try:
        providers = load_providers(config_dir)
    except ConfigError as exc:
        return [provider_config_error(_single_line(str(exc)))]
    return build_provider_health(providers)


def _provider_connectivity(config_dir: Path) -> list[ProviderConnectivity]:
    providers = load_providers(config_dir)
    return build_provider_connectivity(providers)


class _SnapshotState(BaseModel):
    model_config = ConfigDict(frozen=True)

    latest_snapshot_time: datetime | None = None
    last_market_run: MarketRunStatus | None = None


def _snapshot_state(path: Path) -> _SnapshotState:
    if not path.exists():
        return _SnapshotState()

    try:
        store = DuckDBStore(path, read_only=True)
        repo = SnapshotRepo(store)
        latest = repo.latest_committed()
        latest_run = _market_run_status(repo.latest_run())
        store.close()
    except StorageError:
        return _SnapshotState()
    return _SnapshotState(latest_snapshot_time=latest, last_market_run=latest_run)


def _market_run_status(row: dict[str, object] | None) -> MarketRunStatus | None:
    if row is None:
        return None
    return MarketRunStatus.model_validate(row)


def _data_status(
    latest_snapshot_time: datetime | None,
    last_market_run: MarketRunStatus | None,
) -> DataStatus:
    if latest_snapshot_time is None and last_market_run is not None:
        return DataStatus.FAILED if last_market_run.status == "failed" else DataStatus.OFFLINE
    if latest_snapshot_time is None:
        return DataStatus.OFFLINE
    return DataStatus.FRESH


def _single_line(message: str) -> str:
    return " ".join(message.split())
