import json
from pathlib import Path

from dataanalysisbase.delivery.cli import main
from dataanalysisbase.delivery.plan import (
    build_sync_industry_mapping_plan,
    build_sync_market_plan,
    build_sync_trade_calendar_plan,
)

ROOT_CONFIG = Path(__file__).resolve().parents[3] / "config"


def test_sync_market_plan_selects_market_spot_provider() -> None:
    plan = build_sync_market_plan(ROOT_CONFIG)

    assert plan.command == "sync-market"
    assert plan.dry_run is True
    assert plan.selected_provider.name == "akshare"
    assert "market_spot" in plan.selected_provider.datasets
    assert plan.schedule_job == "market_bulk_snapshot"
    assert plan.interval_minutes == 30
    assert plan.will_call_provider is False
    assert plan.will_write_database is False
    assert "market_snapshots" in plan.target_tables


def test_plan_sync_market_json_outputs_dry_run_payload(capsys) -> None:
    exit_code = main(["plan", "sync-market", "--config-dir", str(ROOT_CONFIG), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["command"] == "sync-market"
    assert payload["dry_run"] is True
    assert payload["selected_provider"]["name"] == "akshare"
    assert payload["will_call_provider"] is False
    assert payload["will_write_database"] is False


def test_sync_trade_calendar_plan_targets_sync_schedule() -> None:
    plan = build_sync_trade_calendar_plan(ROOT_CONFIG, year=2026)

    assert plan.command == "sync-trade-calendar"
    assert plan.dry_run is True
    assert plan.provider == "akshare"
    assert plan.year == 2026
    assert plan.target_file.endswith("config\\sync_schedule.yaml") or plan.target_file.endswith(
        "config/sync_schedule.yaml"
    )
    assert plan.will_call_provider is False
    assert plan.will_write_file is False


def test_sync_industry_mapping_plan_targets_configured_mapping_file(monkeypatch) -> None:
    from dataanalysisbase.config_loader.settings import Settings

    monkeypatch.setattr(
        "dataanalysisbase.delivery.plan.load_settings",
        lambda: Settings(config_dir=ROOT_CONFIG, tushare_token=None),
    )

    plan = build_sync_industry_mapping_plan(ROOT_CONFIG)

    assert plan.command == "sync-industry-mapping"
    assert plan.dry_run is True
    assert plan.provider == "akshare"
    assert plan.provider_chain == ["akshare", "efinance", "baostock"]
    assert [candidate.name for candidate in plan.provider_candidates] == [
        "akshare",
        "tushare",
        "efinance",
        "baostock",
    ]
    assert plan.provider_candidates[0].enabled is True
    assert plan.provider_candidates[0].token_configured is None
    assert plan.provider_candidates[1].enabled is False
    assert plan.provider_candidates[1].token_env == "DAB_TUSHARE_TOKEN"
    assert plan.provider_candidates[1].token_configured is False
    assert plan.provider_candidates[2].enabled is False
    assert plan.provider_candidates[2].token_configured is None
    assert plan.provider_candidates[3].enabled is False
    assert plan.provider_candidates[3].token_configured is None
    assert plan.target_file.endswith("data\\industry_mapping.csv") or plan.target_file.endswith(
        "data/industry_mapping.csv"
    )
    assert plan.will_call_provider is False
    assert plan.will_write_file is False


def test_sync_industry_mapping_plan_can_override_provider() -> None:
    plan = build_sync_industry_mapping_plan(ROOT_CONFIG, provider="tushare")

    assert plan.provider == "tushare"
    assert plan.provider_chain == ["tushare"]
    assert [candidate.name for candidate in plan.provider_candidates] == [
        "akshare",
        "tushare",
        "efinance",
        "baostock",
    ]


def test_sync_industry_mapping_plan_prefers_tushare_when_token_exists(monkeypatch) -> None:
    from dataanalysisbase.config_loader.settings import Settings

    monkeypatch.setattr(
        "dataanalysisbase.delivery.plan.load_settings",
        lambda: Settings(config_dir=ROOT_CONFIG, tushare_token="token"),
    )

    plan = build_sync_industry_mapping_plan(ROOT_CONFIG)

    assert plan.provider == "tushare"
    assert plan.provider_chain == ["tushare", "akshare", "efinance", "baostock"]


def test_sync_industry_mapping_plan_can_override_baostock_provider() -> None:
    plan = build_sync_industry_mapping_plan(ROOT_CONFIG, provider="baostock")

    assert plan.provider == "baostock"
    assert plan.provider_chain == ["baostock"]
