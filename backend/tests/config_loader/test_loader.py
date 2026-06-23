from pathlib import Path

import pytest

from dataanalysisbase.common.errors import ConfigError
from dataanalysisbase.config_loader.loader import (
    load_providers,
    load_surveillance_rules,
    load_sync_schedule,
    load_watchlist,
)


ROOT_CONFIG = Path(__file__).resolve().parents[3] / "config"


def test_load_providers_reads_runtime_config() -> None:
    providers = load_providers(ROOT_CONFIG)

    assert providers.providers["akshare"].enabled is True
    assert providers.providers["akshare"].rate_limit.requests_per_minute == 30


def test_load_sync_schedule_requires_valid_jobs() -> None:
    schedule = load_sync_schedule(ROOT_CONFIG)

    assert schedule.timezone == "Asia/Shanghai"
    assert schedule.jobs["market_bulk_snapshot"].interval_minutes == 30


def test_load_surveillance_rules_injects_rule_ids() -> None:
    rules = load_surveillance_rules(ROOT_CONFIG)

    assert rules.rules["limit_up"].rule_id == "limit_up"
    assert rules.rules["limit_up"].condition.op == "gte"


def test_load_watchlist_reads_focus_securities() -> None:
    watchlist = load_watchlist(ROOT_CONFIG)

    assert watchlist.watchlist[0].security_id == "600519.SH"


def test_missing_config_file_raises_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_providers(tmp_path)
