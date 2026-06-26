import pytest

from dataanalysisbase.common.errors import ConfigError
from dataanalysisbase.config_loader.providers_cfg import ProviderEntry, ProvidersConfig
from dataanalysisbase.domain.enums import DatasetType
from dataanalysisbase.providers import ProviderRegistry


def test_registry_selects_enabled_market_spot_provider_by_priority() -> None:
    registry = ProviderRegistry(
        ProvidersConfig(
            version="1.0",
            providers={
                "slow": ProviderEntry(
                    enabled=True,
                    priority=20,
                    datasets=[DatasetType.MARKET_SPOT],
                ),
                "akshare": ProviderEntry(
                    enabled=True,
                    priority=10,
                    datasets=[DatasetType.MARKET_SPOT],
                ),
                "disabled": ProviderEntry(
                    enabled=False,
                    priority=1,
                    datasets=[DatasetType.MARKET_SPOT],
                ),
            },
        )
    )

    name, provider = registry.market_snapshot_provider_config()

    assert name == "akshare"
    assert provider.priority == 10
    assert registry.market_snapshot_provider().name == "akshare"


def test_registry_injects_akshare_industry_mapping_file(tmp_path, monkeypatch) -> None:
    mapping_path = tmp_path / "industry_mapping.csv"
    mapping_path.write_text("security_id,industry\n600519.SH,白酒\n", encoding="utf-8")
    monkeypatch.setattr(
        "dataanalysisbase.providers.registry.load_settings",
        lambda: type("Settings", (), {"data_dir": tmp_path})(),
    )
    registry = ProviderRegistry(
        ProvidersConfig(
            version="1.0",
            providers={
                "akshare": ProviderEntry(
                    enabled=True,
                    priority=10,
                    datasets=[DatasetType.MARKET_SPOT],
                    industry_mapping_path=mapping_path.name,
                ),
            },
        )
    )

    provider = registry.market_snapshot_provider()
    adapter = provider.provider.provider

    assert adapter._fetch_industry_by_code() == {"600519.SH": "白酒"}


def test_registry_requires_enabled_market_spot_provider() -> None:
    registry = ProviderRegistry(
        ProvidersConfig(
            version="1.0",
            providers={
                "akshare": ProviderEntry(enabled=False, datasets=[DatasetType.MARKET_SPOT]),
                "tushare": ProviderEntry(enabled=True, datasets=[DatasetType.DAILY_BARS]),
            },
        )
    )

    with pytest.raises(ConfigError, match="market_spot"):
        registry.market_snapshot_provider_config()


def test_registry_rejects_unsupported_market_spot_provider() -> None:
    registry = ProviderRegistry(
        ProvidersConfig(
            version="1.0",
            providers={
                "custom": ProviderEntry(
                    enabled=True,
                    priority=1,
                    datasets=[DatasetType.MARKET_SPOT],
                ),
            },
        )
    )

    with pytest.raises(ConfigError, match="Unsupported market_spot provider"):
        registry.market_snapshot_provider()
