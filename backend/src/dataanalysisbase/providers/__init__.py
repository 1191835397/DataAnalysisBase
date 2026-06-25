"""External data provider adapters."""

from dataanalysisbase.providers.akshare_adapter import AkshareAdapter
from dataanalysisbase.providers.market import MarketDataProvider, MarketSnapshotBatch
from dataanalysisbase.providers.registry import ProviderRegistry

__all__ = ["AkshareAdapter", "MarketDataProvider", "MarketSnapshotBatch", "ProviderRegistry"]
