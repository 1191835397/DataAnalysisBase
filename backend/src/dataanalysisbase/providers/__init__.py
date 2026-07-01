"""External data provider adapters."""

from dataanalysisbase.providers.akshare_adapter import AkshareAdapter
from dataanalysisbase.providers.baostock_adapter import BaostockAdapter
from dataanalysisbase.providers.efinance_adapter import EfinanceAdapter
from dataanalysisbase.providers.market import MarketDataProvider, MarketSnapshotBatch
from dataanalysisbase.providers.registry import ProviderRegistry
from dataanalysisbase.providers.tushare_adapter import TushareAdapter

__all__ = [
    "AkshareAdapter",
    "BaostockAdapter",
    "EfinanceAdapter",
    "MarketDataProvider",
    "MarketSnapshotBatch",
    "ProviderRegistry",
    "TushareAdapter",
]
