"""Manual sync command helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from dataanalysisbase.config_loader import load_providers, load_settings
from dataanalysisbase.config_loader.providers_cfg import ProviderEntry
from dataanalysisbase.domain.contracts import SyncResult
from dataanalysisbase.ingest import MarketBulkSync
from dataanalysisbase.providers import AkshareAdapter, MarketDataProvider, ProviderRegistry
from dataanalysisbase.providers.industry_mapping import (
    IndustryMappingProvider,
    IndustryMappingSyncResult,
    write_industry_mapping_csv,
)
from dataanalysisbase.storage import AggregateRepo, DuckDBStore, SnapshotRepo


def run_market_sync(
    snapshot_time: datetime,
    *,
    config_dir: Path | None = None,
    duckdb_path: Path | None = None,
    provider: MarketDataProvider | None = None,
) -> SyncResult:
    """Execute one whole-market sync run."""

    settings = load_settings()
    resolved_config_dir = config_dir or settings.config_dir
    resolved_duckdb_path = duckdb_path or settings.duckdb_path
    selected_provider = (
        provider or ProviderRegistry(load_providers(resolved_config_dir)).market_snapshot_provider()
    )

    store = DuckDBStore(resolved_duckdb_path)
    try:
        store.init_schema()
        sync = MarketBulkSync(selected_provider, SnapshotRepo(store), AggregateRepo(store))
        return sync.run_once(snapshot_time)
    finally:
        store.close()


def run_industry_mapping_sync(
    *,
    config_dir: Path | None = None,
    provider: IndustryMappingProvider | None = None,
) -> IndustryMappingSyncResult:
    """Fetch provider industry membership and write the local fallback mapping file."""

    settings = load_settings()
    resolved_config_dir = config_dir or settings.config_dir
    providers = load_providers(resolved_config_dir)
    provider_config = _akshare_config(providers.providers)
    target_path = _resolve_data_path(settings.data_dir, provider_config.industry_mapping_path)
    selected_provider = provider or AkshareAdapter()

    try:
        mapping = selected_provider.fetch_industry_mapping()
        records = write_industry_mapping_csv(target_path, mapping)
    except Exception as exc:
        return IndustryMappingSyncResult(
            status="failed",
            source=selected_provider.name,
            path=str(target_path),
            records=0,
            errors=[str(exc)],
        )

    return IndustryMappingSyncResult(
        status="success",
        source=selected_provider.name,
        path=str(target_path),
        records=records,
    )


def _akshare_config(providers: dict[str, ProviderEntry]) -> ProviderEntry:
    provider = providers.get("akshare")
    if provider is None:
        msg = "providers.yaml missing provider: akshare"
        raise ValueError(msg)
    return provider


def _resolve_data_path(data_dir: Path, path: Path | None) -> Path:
    if path is None:
        msg = "akshare.industry_mapping_path is not configured"
        raise ValueError(msg)
    return path if path.is_absolute() else data_dir / path
