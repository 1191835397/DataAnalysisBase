"""Manual sync command helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from dataanalysisbase.config_loader import load_providers, load_settings
from dataanalysisbase.config_loader.providers_cfg import ProviderEntry
from dataanalysisbase.domain.contracts import SyncResult
from dataanalysisbase.domain.enums import DatasetType
from dataanalysisbase.ingest import MarketBulkSync
from dataanalysisbase.providers import (
    AkshareAdapter,
    EfinanceAdapter,
    MarketDataProvider,
    ProviderRegistry,
    TushareAdapter,
)
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
    provider_name: str | None = None,
) -> IndustryMappingSyncResult:
    """Fetch provider industry membership and write the local fallback mapping file."""

    settings = load_settings()
    resolved_config_dir = config_dir or settings.config_dir
    providers = load_providers(resolved_config_dir)
    provider_config = _akshare_config(providers.providers)
    target_path = _resolve_data_path(settings.data_dir, provider_config.industry_mapping_path)
    try:
        selected_providers = (
            [provider]
            if provider is not None
            else _industry_mapping_providers(
                providers.providers,
                provider_name=provider_name,
                tushare_token=settings.tushare_token,
            )
        )
    except ValueError as exc:
        return IndustryMappingSyncResult(
            status="failed",
            source=provider_name or "none",
            path=str(target_path),
            records=0,
            errors=[str(exc)],
        )

    if not selected_providers:
        return IndustryMappingSyncResult(
            status="failed",
            source="none",
            path=str(target_path),
            records=0,
            errors=["No enabled provider supports industry_mapping"],
        )

    errors: list[str] = []
    for selected_provider in selected_providers:
        result = _try_write_industry_mapping(selected_provider, target_path)
        if result.status == "success":
            return result
        errors.extend(f"{selected_provider.name}: {error}" for error in result.errors)

    return IndustryMappingSyncResult(
        status="failed",
        source=",".join(provider.name for provider in selected_providers),
        path=str(target_path),
        records=0,
        errors=errors,
    )


def _try_write_industry_mapping(
    selected_provider: IndustryMappingProvider,
    target_path: Path,
) -> IndustryMappingSyncResult:
    try:
        mapping = selected_provider.fetch_industry_mapping()
        if not mapping:
            return IndustryMappingSyncResult(
                status="failed",
                source=selected_provider.name,
                path=str(target_path),
                records=0,
                errors=["provider returned 0 industry mapping records"],
            )
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


def _industry_mapping_providers(
    providers: dict[str, ProviderEntry],
    *,
    provider_name: str | None = None,
    tushare_token: str | None,
) -> list[IndustryMappingProvider]:
    candidates = [
        (name, provider)
        for name, provider in providers.items()
        if _matches_industry_mapping_provider(name, provider, provider_name)
    ]
    return [
        _build_industry_mapping_provider(name, provider_config, tushare_token=tushare_token)
        for name, provider_config in sorted(candidates, key=lambda item: item[1].priority)
    ]


def _matches_industry_mapping_provider(
    name: str,
    provider: ProviderEntry,
    provider_name: str | None,
) -> bool:
    if DatasetType.INDUSTRY_MAPPING not in provider.datasets:
        return False
    if provider_name is not None:
        return name == provider_name
    return provider.enabled


def _build_industry_mapping_provider(
    name: str,
    provider_config: ProviderEntry,
    *,
    tushare_token: str | None,
) -> IndustryMappingProvider:
    if name == "akshare":
        return AkshareAdapter()
    if name == "efinance":
        return EfinanceAdapter()
    if name == "tushare":
        token = tushare_token
        if provider_config.token_env and token is None:
            token = None
        return TushareAdapter(token=token)
    msg = f"Unsupported industry_mapping provider: {name}"
    raise ValueError(msg)


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
