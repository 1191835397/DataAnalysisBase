import json
from pathlib import Path

from dataanalysisbase.delivery.cli import main
from dataanalysisbase.observability.provider_connectivity import ProviderConnectivity

ROOT_CONFIG = Path(__file__).resolve().parents[3] / "config"


def test_status_json_outputs_machine_readable_payload(capsys) -> None:
    exit_code = main(["status", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["service"] == "dataanalysisbase"
    assert "data_status" in payload
    assert "providers" in payload
    assert payload["provider_connectivity"] == []
    assert "last_market_run" in payload


def test_config_validate_json_succeeds(capsys) -> None:
    exit_code = main(["config", "validate", "--config-dir", str(ROOT_CONFIG), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert any(item["name"] == "providers.yaml" and item["status"] == "ok" for item in payload)


def test_doctor_json_includes_provider_health(capsys) -> None:
    exit_code = main(["doctor", "--config-dir", str(ROOT_CONFIG), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code in {0, 1}
    assert any(item["name"] == "provider:akshare" for item in payload)


def test_plan_sync_industry_mapping_json_outputs_dry_run_payload(capsys) -> None:
    exit_code = main(["plan", "sync-industry-mapping", "--config-dir", str(ROOT_CONFIG), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["command"] == "sync-industry-mapping"
    assert payload["dry_run"] is True
    assert [candidate["name"] for candidate in payload["provider_candidates"]] == [
        "akshare",
        "tushare",
        "efinance",
    ]
    assert payload["will_call_provider"] is False
    assert payload["will_write_file"] is False


def test_plan_sync_industry_mapping_json_accepts_provider_override(capsys) -> None:
    exit_code = main(
        [
            "plan",
            "sync-industry-mapping",
            "--config-dir",
            str(ROOT_CONFIG),
            "--provider",
            "tushare",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["provider"] == "tushare"


def test_plan_sync_industry_mapping_json_accepts_efinance_override(capsys) -> None:
    exit_code = main(
        [
            "plan",
            "sync-industry-mapping",
            "--config-dir",
            str(ROOT_CONFIG),
            "--provider",
            "efinance",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["provider"] == "efinance"


def test_doctor_online_json_includes_provider_connectivity(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "dataanalysisbase.observability.system_status.build_provider_connectivity",
        lambda _providers: [
            ProviderConnectivity(
                name="akshare",
                status="ok",
                enabled=True,
                endpoint="https://www.eastmoney.com/",
                message="HTTP 200 in 12 ms",
                elapsed_ms=12.0,
            )
        ],
    )

    exit_code = main(["doctor", "--config-dir", str(ROOT_CONFIG), "--online", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code in {0, 1}
    assert any(item["name"] == "provider_connectivity:akshare" for item in payload)
