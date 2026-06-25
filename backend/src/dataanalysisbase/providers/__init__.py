"""External data provider adapters."""

from dataanalysisbase.providers.akshare_adapter import AkshareAdapter
from dataanalysisbase.providers.market import MarketDataProvider, MarketSnapshotBatch

__all__ = ["AkshareAdapter", "MarketDataProvider", "MarketSnapshotBatch"]
