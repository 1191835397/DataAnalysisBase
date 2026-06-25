"""Provider registry and config-driven routing."""

from __future__ import annotations

from dataanalysisbase.common.errors import ConfigError
from dataanalysisbase.config_loader.providers_cfg import ProviderEntry, ProvidersConfig
from dataanalysisbase.domain.enums import DatasetType
from dataanalysisbase.providers.akshare_adapter import AkshareAdapter
from dataanalysisbase.providers.market import MarketDataProvider


class ProviderRegistry:
    """Resolve configured providers for ingestion workflows."""

    def __init__(self, config: ProvidersConfig) -> None:
        self.config = config

    def market_snapshot_provider(self) -> MarketDataProvider:
        """Return the configured provider for whole-market spot snapshots."""

        name, _ = self.market_snapshot_provider_config()
        return _build_market_provider(name)

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


def _build_market_provider(name: str) -> MarketDataProvider:
    if name == "akshare":
        return AkshareAdapter()
    raise ConfigError(f"Unsupported market_spot provider: {name}")
