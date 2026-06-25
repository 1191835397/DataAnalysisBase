"""Dry-run execution plans for operational CLI commands."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from dataanalysisbase.common.errors import ConfigError
from dataanalysisbase.config_loader import load_providers, load_settings, load_sync_schedule
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
