"""Manual sync command helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from dataanalysisbase.config_loader import load_providers, load_settings
from dataanalysisbase.domain.contracts import SyncResult
from dataanalysisbase.ingest import MarketBulkSync
from dataanalysisbase.providers import MarketDataProvider, ProviderRegistry
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
