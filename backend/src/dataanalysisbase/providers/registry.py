"""Provider registry and config-driven routing."""

from __future__ import annotations

from pathlib import Path

from dataanalysisbase.common.errors import ConfigError
from dataanalysisbase.config_loader import load_settings
from dataanalysisbase.config_loader.providers_cfg import ProviderEntry, ProvidersConfig
from dataanalysisbase.domain.enums import DatasetType
from dataanalysisbase.providers.akshare_adapter import AkshareAdapter
from dataanalysisbase.providers.industry_mapping import load_industry_mapping_file
from dataanalysisbase.providers.market import MarketDataProvider
from dataanalysisbase.providers.wrappers import RateLimitedMarketProvider, RetryingMarketProvider


class ProviderRegistry:
    """Resolve configured providers for ingestion workflows."""

    def __init__(self, config: ProvidersConfig) -> None:
        self.config = config

    def market_snapshot_provider(self) -> MarketDataProvider:
        """Return the configured provider for whole-market spot snapshots."""

        name, provider_config = self.market_snapshot_provider_config()
        provider = _build_market_provider(name, provider_config)
        return _wrap_market_provider(provider, provider_config)

    def market_snapshot_provider_config(self) -> tuple[str, ProviderEntry]:
        """Return provider name and config for whole-market spot snapshots."""

        candidates = [
            (name, provider)
            for name, provider in self.config.providers.items()
            if provider.enabled and DatasetType.MARKET_SPOT in provider.datasets
        ]
        if not candidates:
            raise ConfigError("No enabled provider supports market_spot")
        return min(candidates, key=lambda item: item[1].priority)


def _build_market_provider(name: str, provider_config: ProviderEntry) -> MarketDataProvider:
    if name == "akshare":
        mapping_path = _resolve_industry_mapping_path(provider_config.industry_mapping_path)
        return AkshareAdapter(
            industry_mapping_fetcher=(
                (lambda: load_industry_mapping_file(mapping_path))
                if mapping_path is not None
                else None
            )
        )
    raise ConfigError(f"Unsupported market_spot provider: {name}")


def _resolve_industry_mapping_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    if path.is_absolute():
        return path
    return load_settings().data_dir / path


def _wrap_market_provider(
    provider: MarketDataProvider,
    provider_config: ProviderEntry,
) -> MarketDataProvider:
    rate_limit = provider_config.rate_limit
    rate_limited: MarketDataProvider = RateLimitedMarketProvider(
        provider,
        requests_per_minute=rate_limit.requests_per_minute,
    )
    return RetryingMarketProvider(
        rate_limited,
        retries=rate_limit.retry,
        delay_sec=rate_limit.retry_delay_sec,
    )
