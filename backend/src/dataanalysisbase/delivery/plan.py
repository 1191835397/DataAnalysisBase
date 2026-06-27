"""Dry-run execution plans for operational CLI commands."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from dataanalysisbase.common.errors import ConfigError
from dataanalysisbase.config_loader import load_providers, load_settings, load_sync_schedule
from dataanalysisbase.config_loader.providers_cfg import ProvidersConfig
from dataanalysisbase.domain.enums import DatasetType
from dataanalysisbase.providers import ProviderRegistry

SYNC_MARKET_TABLES = [
    "market_snapshot_runs",
    "market_snapshots",
    "latest_market_snapshot",
    "market_overview_snapshots",
    "industry_snapshots",
]


class ProviderPlan(BaseModel):
    """Provider selected for a dry-run plan."""

    model_config = ConfigDict(frozen=True)

    name: str
    priority: int
    datasets: list[str]
    rate_limit_requests_per_minute: int | None
    retry: int


class ProviderCandidatePlan(BaseModel):
    """Provider candidate for a dataset-specific dry-run plan."""

    model_config = ConfigDict(frozen=True)

    name: str
    enabled: bool
    priority: int
    supports_dataset: bool
    token_env: str | None
    token_configured: bool | None


class SyncMarketPlan(BaseModel):
    """Dry-run plan for one whole-market snapshot sync."""

    model_config = ConfigDict(frozen=True)

    command: str
    dry_run: bool
    run_mode: str
    config_dir: str
    duckdb_path: str
    selected_provider: ProviderPlan
    schedule_job: str
    interval_minutes: int | None
    trading_sessions: list[str]
    trading_days_only: bool
    on_complete: str | None
    target_tables: list[str]
    will_call_provider: bool
    will_write_database: bool
    notes: list[str]


class SyncIndustryMappingPlan(BaseModel):
    """Dry-run plan for local industry mapping refresh."""

    model_config = ConfigDict(frozen=True)

    command: str
    dry_run: bool
    run_mode: str
    config_dir: str
    provider: str
    provider_candidates: list[ProviderCandidatePlan]
    target_file: str
    will_call_provider: bool
    will_write_file: bool
    notes: list[str]


def build_sync_market_plan(config_dir: Path | None = None) -> SyncMarketPlan:
    """Build a read-only preview for market bulk sync."""

    settings = load_settings()
    resolved_config_dir = config_dir or settings.config_dir
    providers = load_providers(resolved_config_dir)
    schedule = load_sync_schedule(resolved_config_dir)
    provider_name, provider = ProviderRegistry(providers).market_snapshot_provider_config()
    job = schedule.jobs.get("market_bulk_snapshot")
    if job is None:
        raise ConfigError("sync_schedule.yaml missing job: market_bulk_snapshot")

    return SyncMarketPlan(
        command="sync-market",
        dry_run=True,
        run_mode=settings.run_mode,
        config_dir=str(resolved_config_dir),
        duckdb_path=str(settings.duckdb_path),
        selected_provider=ProviderPlan(
            name=provider_name,
            priority=provider.priority,
            datasets=[dataset.value for dataset in provider.datasets],
            rate_limit_requests_per_minute=provider.rate_limit.requests_per_minute,
            retry=provider.rate_limit.retry,
        ),
        schedule_job="market_bulk_snapshot",
        interval_minutes=job.interval_minutes,
        trading_sessions=[f"{session.start}-{session.end}" for session in job.trading_sessions],
        trading_days_only=job.trading_days_only,
        on_complete=job.on_complete,
        target_tables=SYNC_MARKET_TABLES,
        will_call_provider=False,
        will_write_database=False,
        notes=[
            "dry-run only; no provider request is made",
            "dry-run only; no DuckDB write is performed",
            "real execution should write through MarketBulkSync and storage repositories",
        ],
    )


def build_sync_industry_mapping_plan(config_dir: Path | None = None) -> SyncIndustryMappingPlan:
    """Build a read-only preview for refreshing the local industry mapping file."""

    settings = load_settings()
    resolved_config_dir = config_dir or settings.config_dir
    providers = load_providers(resolved_config_dir)
    akshare = providers.providers.get("akshare")
    if akshare is None:
        raise ConfigError("providers.yaml missing provider: akshare")
    if akshare.industry_mapping_path is None:
        raise ConfigError("akshare.industry_mapping_path is not configured")
    target_file = (
        akshare.industry_mapping_path
        if akshare.industry_mapping_path.is_absolute()
        else settings.data_dir / akshare.industry_mapping_path
    )
    candidates = _provider_candidates(
        providers,
        dataset=DatasetType.INDUSTRY_MAPPING,
        token_values={"TUSHARE_TOKEN": settings.tushare_token},
    )
    enabled_candidates = [candidate for candidate in candidates if candidate.enabled]
    selected_provider = (
        min(enabled_candidates, key=lambda candidate: candidate.priority).name
        if enabled_candidates
        else "none"
    )

    return SyncIndustryMappingPlan(
        command="sync-industry-mapping",
        dry_run=True,
        run_mode=settings.run_mode,
        config_dir=str(resolved_config_dir),
        provider=selected_provider,
        provider_candidates=candidates,
        target_file=str(target_file),
        will_call_provider=False,
        will_write_file=False,
        notes=[
            "dry-run only; no provider request is made",
            "dry-run only; no industry mapping file is written",
            "real execution fetches provider-native industry board membership",
        ],
    )


def _provider_candidates(
    providers: ProvidersConfig,
    *,
    dataset: DatasetType,
    token_values: dict[str, str | None],
) -> list[ProviderCandidatePlan]:
    return [
        ProviderCandidatePlan(
            name=name,
            enabled=provider.enabled,
            priority=provider.priority,
            supports_dataset=dataset in provider.datasets,
            token_env=provider.token_env,
            token_configured=(
                None if provider.token_env is None else bool(token_values.get(provider.token_env))
            ),
        )
        for name, provider in sorted(
            providers.providers.items(),
            key=lambda item: (not item[1].enabled, item[1].priority, item[0]),
        )
        if dataset in provider.datasets
    ]
