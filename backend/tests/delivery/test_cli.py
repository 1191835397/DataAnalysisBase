import json
from pathlib import Path

from dataanalysisbase.delivery.cli import main

ROOT_CONFIG = Path(__file__).resolve().parents[3] / "config"


def test_status_json_outputs_machine_readable_payload(capsys) -> None:
    exit_code = main(["status", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["service"] == "dataanalysisbase"
    assert "data_status" in payload


def test_config_validate_json_succeeds(capsys) -> None:
    exit_code = main(["config", "validate", "--config-dir", str(ROOT_CONFIG), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert any(item["name"] == "providers.yaml" and item["status"] == "ok" for item in payload)
