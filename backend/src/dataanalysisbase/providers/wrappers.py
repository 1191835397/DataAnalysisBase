"""Provider wrappers for retry and local rate limiting."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime

from dataanalysisbase.common.errors import ProviderError
from dataanalysisbase.providers.market import MarketDataProvider, MarketSnapshotBatch


class RetryingMarketProvider:
    """Retry retryable provider errors before surfacing failure."""

    def __init__(
        self,
        provider: MarketDataProvider,
        *,
        retries: int,
        delay_sec: float,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.provider = provider
        self.name = provider.name
        self.retries = max(retries, 0)
        self.delay_sec = max(delay_sec, 0)
        self._sleep = sleep

    def fetch_market_snapshot(self, snapshot_time: datetime) -> MarketSnapshotBatch:
        attempts = self.retries + 1
        last_error: ProviderError | None = None
        for attempt in range(1, attempts + 1):
            try:
                return self.provider.fetch_market_snapshot(snapshot_time)
            except ProviderError as exc:
                if not exc.retryable:
                    raise
                last_error = exc
                if attempt < attempts and self.delay_sec > 0:
                    self._sleep(self.delay_sec)
        if last_error is not None:
            raise last_error
        msg = "retry loop exited without result"
        raise RuntimeError(msg)


class RateLimitedMarketProvider:
    """Apply a per-process minimum interval between provider calls."""

    def __init__(
        self,
        provider: MarketDataProvider,
        *,
        requests_per_minute: int | None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.provider = provider
        self.name = provider.name
        self.requests_per_minute = requests_per_minute
        self._monotonic = monotonic
        self._sleep = sleep
        self._last_call_at: float | None = None

    def fetch_market_snapshot(self, snapshot_time: datetime) -> MarketSnapshotBatch:
        self._wait_if_needed()
        self._last_call_at = self._monotonic()
        return self.provider.fetch_market_snapshot(snapshot_time)

    def _wait_if_needed(self) -> None:
        if self.requests_per_minute is None or self.requests_per_minute <= 0:
            return
        if self._last_call_at is None:
            return
        min_interval = 60 / self.requests_per_minute
        elapsed = self._monotonic() - self._last_call_at
        wait_sec = min_interval - elapsed
        if wait_sec > 0:
            self._sleep(wait_sec)
