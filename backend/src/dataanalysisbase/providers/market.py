"""Market snapshot provider contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from dataanalysisbase.domain.contracts import MarketRow


@dataclass(frozen=True)
class MarketSnapshotBatch:
    """Provider result for one whole-market snapshot fetch."""

    snapshot_time: datetime
    source: str
    expected: int
    rows: list[MarketRow]

    def __post_init__(self) -> None:
        if self.expected < 0:
            msg = "expected must be non-negative"
            raise ValueError(msg)


class MarketDataProvider(Protocol):
    """Protocol implemented by whole-market data providers."""

    name: str

    def fetch_market_snapshot(self, snapshot_time: datetime) -> MarketSnapshotBatch:
        """Fetch one whole-market snapshot for the requested time."""
