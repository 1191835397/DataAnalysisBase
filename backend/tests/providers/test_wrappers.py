from __future__ import annotations

from datetime import datetime

import pytest

from dataanalysisbase.common.errors import ProviderError
from dataanalysisbase.providers import MarketSnapshotBatch
from dataanalysisbase.providers.wrappers import RateLimitedMarketProvider, RetryingMarketProvider


def test_retrying_market_provider_retries_retryable_errors() -> None:
    provider = FlakyProvider(failures=2)
    sleeps: list[float] = []
    wrapped = RetryingMarketProvider(provider, retries=3, delay_sec=0.5, sleep=sleeps.append)

    batch = wrapped.fetch_market_snapshot(datetime(2026, 6, 26, 9, 30))

    assert batch.source == "mock"
    assert provider.calls == 3
    assert sleeps == [0.5, 0.5]


def test_retrying_market_provider_does_not_retry_non_retryable_errors() -> None:
    provider = NonRetryableProvider()
    wrapped = RetryingMarketProvider(provider, retries=3, delay_sec=0.5, sleep=lambda _: None)

    with pytest.raises(ProviderError):
        wrapped.fetch_market_snapshot(datetime(2026, 6, 26, 9, 30))

    assert provider.calls == 1


def test_rate_limited_market_provider_waits_between_calls() -> None:
    provider = SuccessfulProvider()
    clock = FakeClock([10.0, 10.0, 10.0])
    sleeps: list[float] = []
    wrapped = RateLimitedMarketProvider(
        provider,
        requests_per_minute=30,
        monotonic=clock.monotonic,
        sleep=sleeps.append,
    )

    wrapped.fetch_market_snapshot(datetime(2026, 6, 26, 9, 30))
    wrapped.fetch_market_snapshot(datetime(2026, 6, 26, 9, 31))

    assert sleeps == [2.0]


class SuccessfulProvider:
    name = "mock"

    def __init__(self) -> None:
        self.calls = 0

    def fetch_market_snapshot(self, snapshot_time: datetime) -> MarketSnapshotBatch:
        self.calls += 1
        return MarketSnapshotBatch(
            snapshot_time=snapshot_time,
            source=self.name,
            expected=0,
            rows=[],
        )


class FlakyProvider(SuccessfulProvider):
    def __init__(self, *, failures: int) -> None:
        super().__init__()
        self.failures = failures

    def fetch_market_snapshot(self, snapshot_time: datetime) -> MarketSnapshotBatch:
        self.calls += 1
        if self.calls <= self.failures:
            raise ProviderError(self.name, "market_spot", "temporary upstream error")
        return MarketSnapshotBatch(
            snapshot_time=snapshot_time,
            source=self.name,
            expected=0,
            rows=[],
        )


class NonRetryableProvider(SuccessfulProvider):
    def fetch_market_snapshot(self, snapshot_time: datetime) -> MarketSnapshotBatch:
        self.calls += 1
        raise ProviderError(self.name, "market_spot", "invalid row", retryable=False)


class FakeClock:
    def __init__(self, values: list[float]) -> None:
        self.values = values

    def monotonic(self) -> float:
        return self.values.pop(0)
