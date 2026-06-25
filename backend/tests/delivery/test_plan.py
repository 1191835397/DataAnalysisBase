import json
from pathlib import Path

from dataanalysisbase.delivery.cli import main
from dataanalysisbase.delivery.plan import build_sync_market_plan

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
