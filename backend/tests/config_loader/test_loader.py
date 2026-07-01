from datetime import date
from pathlib import Path

import pytest

from dataanalysisbase.common.errors import ConfigError
from dataanalysisbase.config_loader.loader import (
    load_providers,
    load_settings,
    load_surveillance_rules,
    load_sync_schedule,
    load_watchlist,
)
from dataanalysisbase.domain.enums import DatasetType

ROOT_CONFIG = Path(__file__).resolve().parents[3] / "config"


def test_load_providers_reads_runtime_config() -> None:
    providers = load_providers(ROOT_CONFIG)

    assert providers.providers["akshare"].enabled is True
    assert providers.providers["akshare"].rate_limit.requests_per_minute == 30
    assert str(providers.providers["akshare"].industry_mapping_path) == "industry_mapping.csv"
    assert DatasetType.INDUSTRY_MAPPING in providers.providers["akshare"].datasets
    assert providers.providers["efinance"].enabled is False
    assert DatasetType.INDUSTRY_MAPPING in providers.providers["efinance"].datasets
    assert providers.providers["baostock"].enabled is False
    assert DatasetType.INDUSTRY_MAPPING in providers.providers["baostock"].datasets


def test_load_sync_schedule_requires_valid_jobs() -> None:
    schedule = load_sync_schedule(ROOT_CONFIG)

    assert schedule.timezone == "Asia/Shanghai"
    assert all(isinstance(day, date) for day in schedule.holidays)
    assert all(isinstance(day, date) for day in schedule.makeup_trading_days)
    assert schedule.jobs["market_bulk_snapshot"].interval_minutes == 30


def test_load_sync_schedule_reads_calendar_overrides(tmp_path: Path) -> None:
    (tmp_path / "sync_schedule.yaml").write_text(
        """
version: "1.0"
timezone: "Asia/Shanghai"
holidays:
  - "2026-10-01"
makeup_trading_days:
  - "2026-09-27"
jobs:
  market_bulk_snapshot:
    interval_minutes: 30
""",
        encoding="utf-8",
    )

    schedule = load_sync_schedule(tmp_path)

    assert schedule.holidays == [date(2026, 10, 1)]
    assert schedule.makeup_trading_days == [date(2026, 9, 27)]


def test_load_surveillance_rules_injects_rule_ids() -> None:
    rules = load_surveillance_rules(ROOT_CONFIG)

    assert rules.rules["limit_up"].rule_id == "limit_up"
    assert rules.rules["limit_up"].condition.op == "gte"


def test_load_watchlist_reads_focus_securities() -> None:
    watchlist = load_watchlist(ROOT_CONFIG)

    assert watchlist.watchlist[0].security_id == "600519.SH"


def test_load_settings_reads_project_root_env_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    backend_dir = project_root / "backend"
    config_dir = project_root / "config"
    backend_dir.mkdir(parents=True)
    config_dir.mkdir()
    (project_root / ".env").write_text("DAB_TUSHARE_TOKEN=test-token\n", encoding="utf-8")
    monkeypatch.chdir(backend_dir)
    monkeypatch.delenv("DAB_TUSHARE_TOKEN", raising=False)

    settings = load_settings()

    assert settings.config_dir == config_dir
    assert settings.tushare_token == "test-token"


def test_missing_config_file_raises_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_providers(tmp_path)
