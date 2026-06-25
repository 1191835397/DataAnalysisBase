"""Provider health checks that do not call external networks."""

from __future__ import annotations

import importlib.util
import os
import sys
from typing import Literal

from pydantic import BaseModel, ConfigDict

from dataanalysisbase.config_loader.providers_cfg import ProviderEntry, ProvidersConfig
from dataanalysisbase.domain.enums import DatasetType


class ProviderHealth(BaseModel):
    """Local provider readiness status."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: Literal["ok", "warning", "error"]
    enabled: bool
    priority: int
    datasets: list[str]
    message: str


def build_provider_health(config: ProvidersConfig) -> list[ProviderHealth]:
    """Build local readiness checks for configured providers without network calls."""

    return [
        _provider_health(name, provider)
        for name, provider in sorted(
            config.providers.items(),
            key=lambda item: (not item[1].enabled, item[1].priority, item[0]),
        )
    ]


def _provider_health(name: str, provider: ProviderEntry) -> ProviderHealth:
    if not provider.enabled:
        return _health(name, provider, "warning", "disabled in providers.yaml")

    dependency = _dependency_for_provider(name)
    if dependency is None:
        return _health(name, provider, "error", f"unsupported provider: {name}")

    if not _dependency_available(dependency):
        return _health(
            name,
            provider,
            "warning",
            f"optional dependency not installed: {dependency}",
        )

    if provider.token_env and not os.environ.get(provider.token_env):
        return _health(name, provider, "warning", f"token env not configured: {provider.token_env}")

    return _health(name, provider, "ok", "local provider dependency is available")


def provider_config_error(message: str) -> ProviderHealth:
    """Return a provider-health shaped config error for status payloads."""

    return ProviderHealth(
        name="provider_config",
        status="error",
        enabled=False,
        priority=0,
        datasets=[],
        message=message,
    )


def _health(
    name: str,
    provider: ProviderEntry,
    status: Literal["ok", "warning", "error"],
    message: str,
) -> ProviderHealth:
    return ProviderHealth(
        name=name,
        status=status,
        enabled=provider.enabled,
        priority=provider.priority,
        datasets=[dataset.value for dataset in provider.datasets],
        message=message,
    )


def _dependency_for_provider(name: str) -> str | None:
    dependencies = {
        "akshare": "akshare",
        "tushare": "tushare",
        "cninfo": None,
        "yfinance": "yfinance",
    }
    return dependencies.get(name)


def _dependency_available(name: str) -> bool:
    if name in sys.modules:
        return True
    try:
        return importlib.util.find_spec(name) is not None
    except ValueError:
        return False


def supports_market_spot(provider: ProviderHealth) -> bool:
    """Return true when the health entry is for an enabled market spot provider."""

    return provider.enabled and DatasetType.MARKET_SPOT.value in provider.datasets
