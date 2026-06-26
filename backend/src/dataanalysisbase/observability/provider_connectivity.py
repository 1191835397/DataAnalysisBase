"""Online provider connectivity probes.

These checks are explicit opt-in diagnostics. They verify that an upstream host is
reachable without fetching market datasets or writing local state.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict

from dataanalysisbase.config_loader.providers_cfg import ProviderEntry, ProvidersConfig


class ProviderConnectivityError(Exception):
    """Raised when an online provider probe cannot complete."""


class ConnectivityProbeResult(BaseModel):
    """Raw result from a lightweight provider endpoint probe."""

    model_config = ConfigDict(frozen=True)

    status_code: int
    elapsed_ms: float


class ProviderConnectivity(BaseModel):
    """Online provider reachability status."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: Literal["ok", "warning", "error"]
    enabled: bool
    endpoint: str | None
    message: str
    elapsed_ms: float | None = None


ProviderConnectivityProbe = Callable[[str, float], ConnectivityProbeResult]


def build_provider_connectivity(
    config: ProvidersConfig,
    *,
    timeout_sec: float = 3.0,
    probe: ProviderConnectivityProbe | None = None,
) -> list[ProviderConnectivity]:
    """Build explicit online reachability checks for enabled providers."""

    active_probe = probe or httpx_connectivity_probe
    return [
        _provider_connectivity(name, provider, timeout_sec=timeout_sec, probe=active_probe)
        for name, provider in sorted(
            config.providers.items(),
            key=lambda item: (not item[1].enabled, item[1].priority, item[0]),
        )
        if provider.enabled
    ]


def httpx_connectivity_probe(url: str, timeout_sec: float) -> ConnectivityProbeResult:
    """Probe a provider endpoint with a lightweight HTTP GET."""

    started = time.perf_counter()
    try:
        response = httpx.get(url, timeout=timeout_sec, follow_redirects=True)
    except httpx.HTTPError as exc:
        raise ProviderConnectivityError(_single_line(str(exc))) from exc
    return ConnectivityProbeResult(
        status_code=response.status_code,
        elapsed_ms=(time.perf_counter() - started) * 1000,
    )


def _provider_connectivity(
    name: str,
    provider: ProviderEntry,
    *,
    timeout_sec: float,
    probe: ProviderConnectivityProbe,
) -> ProviderConnectivity:
    endpoint = _endpoint_for_provider(name)
    if endpoint is None:
        return ProviderConnectivity(
            name=name,
            status="warning",
            enabled=provider.enabled,
            endpoint=None,
            message=f"online probe not configured: {name}",
        )

    try:
        result = probe(endpoint, timeout_sec)
    except ProviderConnectivityError as exc:
        return ProviderConnectivity(
            name=name,
            status="error",
            enabled=provider.enabled,
            endpoint=endpoint,
            message=f"probe failed: {_single_line(str(exc))}",
        )
    except Exception as exc:
        return ProviderConnectivity(
            name=name,
            status="error",
            enabled=provider.enabled,
            endpoint=endpoint,
            message=f"probe failed: {_single_line(str(exc))}",
        )

    return ProviderConnectivity(
        name=name,
        status=_status_for_http(result.status_code),
        enabled=provider.enabled,
        endpoint=endpoint,
        message=f"HTTP {result.status_code} in {result.elapsed_ms:.0f} ms",
        elapsed_ms=result.elapsed_ms,
    )


def _endpoint_for_provider(name: str) -> str | None:
    endpoints = {
        "akshare": "https://www.eastmoney.com/",
        "tushare": "https://api.tushare.pro/",
        "cninfo": "https://www.cninfo.com.cn/",
        "yfinance": "https://query1.finance.yahoo.com/",
    }
    return endpoints.get(name)


def _status_for_http(status_code: int) -> Literal["ok", "warning", "error"]:
    if status_code < 400:
        return "ok"
    if status_code < 500:
        return "warning"
    return "error"


def _single_line(message: str) -> str:
    return " ".join(message.split())
