"""External data provider adapters."""

from dataanalysisbase.providers.akshare_adapter import AkshareAdapter
from dataanalysisbase.providers.market import MarketDataProvider, MarketSnapshotBatch
from dataanalysisbase.providers.registry import ProviderRegistry
from dataanalysisbase.providers.tushare_adapter import TushareAdapter

__all__ = [
    "AkshareAdapter",
    "MarketDataProvider",
    "MarketSnapshotBatch",
    "ProviderRegistry",
    "TushareAdapter",
]
