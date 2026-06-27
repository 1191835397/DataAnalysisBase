import sys
from types import ModuleType

from dataanalysisbase.config_loader.providers_cfg import ProviderEntry, ProvidersConfig
from dataanalysisbase.domain.enums import DatasetType
from dataanalysisbase.observability.provider_health import (
    build_provider_health,
    supports_market_spot,
)


def test_provider_health_reports_available_dependency(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "akshare", ModuleType("akshare"))
    config = ProvidersConfig(
        version="1.0",
        providers={
            "akshare": ProviderEntry(
                enabled=True,
                priority=2,
                datasets=[DatasetType.MARKET_SPOT],
            )
        },
    )

    health = build_provider_health(config)

    assert len(health) == 1
    assert health[0].name == "akshare"
    assert health[0].status == "ok"
    assert supports_market_spot(health[0]) is True


def test_provider_health_warns_for_missing_token(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "tushare", ModuleType("tushare"))
    monkeypatch.delenv("DAB_TUSHARE_TOKEN", raising=False)
    config = ProvidersConfig(
        version="1.0",
        providers={
            "tushare": ProviderEntry(
                enabled=True,
                token_env="DAB_TUSHARE_TOKEN",
                datasets=[DatasetType.DAILY_BARS],
            )
        },
    )

    health = build_provider_health(config)

    assert health[0].status == "warning"
    assert health[0].message == "token env not configured: DAB_TUSHARE_TOKEN"


def test_provider_health_ignores_disabled_provider_missing_dependency() -> None:
    config = ProvidersConfig(
        version="1.0",
        providers={
            "yfinance": ProviderEntry(
                enabled=False,
                datasets=[DatasetType.DAILY_BARS],
            )
        },
    )

    health = build_provider_health(config)

    assert health[0].status == "warning"
    assert health[0].message == "disabled in providers.yaml"


def test_provider_health_errors_for_unsupported_enabled_provider() -> None:
    config = ProvidersConfig(
        version="1.0",
        providers={
            "unknown": ProviderEntry(
                enabled=True,
                datasets=[DatasetType.MARKET_SPOT],
            )
        },
    )

    health = build_provider_health(config)

    assert health[0].status == "error"
    assert health[0].message == "unsupported provider: unknown"
