from dataanalysisbase.config_loader.providers_cfg import ProviderEntry, ProvidersConfig
from dataanalysisbase.observability.provider_connectivity import (
    ConnectivityProbeResult,
    ProviderConnectivityError,
    build_provider_connectivity,
)


def test_provider_connectivity_reports_reachable_endpoint() -> None:
    config = ProvidersConfig(
        version="1.0",
        providers={"akshare": ProviderEntry(enabled=True)},
    )

    connectivity = build_provider_connectivity(config, probe=lambda _url, _timeout: _result(200))

    assert len(connectivity) == 1
    assert connectivity[0].name == "akshare"
    assert connectivity[0].status == "ok"
    assert connectivity[0].endpoint == "https://www.eastmoney.com/"
    assert connectivity[0].message == "HTTP 200 in 12 ms"


def test_provider_connectivity_warns_for_client_error() -> None:
    config = ProvidersConfig(
        version="1.0",
        providers={"akshare": ProviderEntry(enabled=True)},
    )

    connectivity = build_provider_connectivity(config, probe=lambda _url, _timeout: _result(403))

    assert connectivity[0].status == "warning"
    assert connectivity[0].message == "HTTP 403 in 12 ms"


def test_provider_connectivity_errors_for_probe_failure() -> None:
    config = ProvidersConfig(
        version="1.0",
        providers={"akshare": ProviderEntry(enabled=True)},
    )

    connectivity = build_provider_connectivity(config, probe=_failing_probe)

    assert connectivity[0].status == "error"
    assert connectivity[0].message == "probe failed: connection reset"


def test_provider_connectivity_skips_disabled_providers() -> None:
    config = ProvidersConfig(
        version="1.0",
        providers={"akshare": ProviderEntry(enabled=False)},
    )

    connectivity = build_provider_connectivity(config, probe=lambda _url, _timeout: _result(200))

    assert connectivity == []


def test_provider_connectivity_warns_for_unknown_provider() -> None:
    config = ProvidersConfig(
        version="1.0",
        providers={"unknown": ProviderEntry(enabled=True)},
    )

    connectivity = build_provider_connectivity(config, probe=lambda _url, _timeout: _result(200))

    assert connectivity[0].status == "warning"
    assert connectivity[0].endpoint is None
    assert connectivity[0].message == "online probe not configured: unknown"


def _result(status_code: int) -> ConnectivityProbeResult:
    return ConnectivityProbeResult(status_code=status_code, elapsed_ms=12.0)


def _failing_probe(_url: str, _timeout: float) -> ConnectivityProbeResult:
    raise ProviderConnectivityError("connection reset")
