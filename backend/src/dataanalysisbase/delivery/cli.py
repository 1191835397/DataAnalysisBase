"""Command line diagnostics for local development and operations."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from dataanalysisbase.delivery.plan import build_sync_market_plan
from dataanalysisbase.delivery.sync import run_market_sync
from dataanalysisbase.observability.system_status import (
    build_runtime_status,
    has_errors,
    run_doctor,
    validate_config,
)


def main(argv: list[str] | None = None) -> int:
    """Run the `dab` command line interface."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "config" and args.config_command == "validate":
        return _config_validate(args)
    if args.command == "doctor":
        return _doctor(args)
    if args.command == "status":
        return _status(args)
    if args.command == "plan" and args.plan_command == "sync-market":
        return _plan_sync_market(args)
    if args.command == "sync" and args.sync_command == "market":
        return _sync_market(args)

    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dab", description="DataAnalysisBase operations CLI")
    subparsers = parser.add_subparsers(dest="command")

    config_parser = subparsers.add_parser("config", help="Configuration helpers")
    config_subparsers = config_parser.add_subparsers(dest="config_command")
    config_validate = config_subparsers.add_parser("validate", help="Validate runtime YAML config")
    config_validate.add_argument("--config-dir", type=Path, default=None)
    config_validate.add_argument("--json", action="store_true", dest="json_output")

    doctor = subparsers.add_parser("doctor", help="Run local diagnostics")
    doctor.add_argument("--json", action="store_true", dest="json_output")

    status = subparsers.add_parser("status", help="Print runtime status")
    status.add_argument("--json", action="store_true", dest="json_output")

    plan_parser = subparsers.add_parser("plan", help="Preview operational actions")
    plan_subparsers = plan_parser.add_subparsers(dest="plan_command")
    plan_sync_market = plan_subparsers.add_parser(
        "sync-market",
        help="Preview whole-market snapshot sync",
    )
    plan_sync_market.add_argument("--config-dir", type=Path, default=None)
    plan_sync_market.add_argument("--json", action="store_true", dest="json_output")

    sync_parser = subparsers.add_parser("sync", help="Run manual sync jobs")
    sync_subparsers = sync_parser.add_subparsers(dest="sync_command")
    sync_market = sync_subparsers.add_parser("market", help="Run one whole-market sync")
    sync_market.add_argument("--config-dir", type=Path, default=None)
    sync_market.add_argument("--snapshot-time", type=_parse_datetime, default=None)
    sync_market.add_argument("--execute", action="store_true")
    sync_market.add_argument("--json", action="store_true", dest="json_output")
    return parser


def _config_validate(args: argparse.Namespace) -> int:
    results = validate_config(args.config_dir)
    _emit(results, json_output=args.json_output)
    return 1 if has_errors(results) else 0


def _doctor(args: argparse.Namespace) -> int:
    results = run_doctor()
    _emit(results, json_output=args.json_output)
    return 1 if has_errors(results) else 0


def _status(args: argparse.Namespace) -> int:
    status = build_runtime_status()
    if args.json_output:
        print(json.dumps(status.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        print(f"service: {status.service}")
        print(f"run_mode: {status.run_mode}")
        print(f"data_status: {status.data_status.value}")
        print(f"latest_snapshot_time: {status.latest_snapshot_time or 'none'}")
        print(f"duckdb_path: {status.duckdb_path}")
        print(f"config_dir: {status.config_dir}")
    return 0


def _plan_sync_market(args: argparse.Namespace) -> int:
    plan = build_sync_market_plan(args.config_dir)
    if args.json_output:
        print(json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        print("plan: sync-market")
        print("dry_run: true")
        print(f"run_mode: {plan.run_mode}")
        print(f"provider: {plan.selected_provider.name}")
        print(f"schedule: {plan.schedule_job} every {plan.interval_minutes} minutes")
        print(f"target_tables: {', '.join(plan.target_tables)}")
        print("will_call_provider: false")
        print("will_write_database: false")
    return 0


def _sync_market(args: argparse.Namespace) -> int:
    if not args.execute:
        plan = build_sync_market_plan(args.config_dir)
        if args.json_output:
            print(json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2))
        else:
            print("dry-run: true")
            print("pass --execute to call provider and write DuckDB")
            print(f"provider: {plan.selected_provider.name}")
            print(f"target_tables: {', '.join(plan.target_tables)}")
        return 0

    snapshot_time = args.snapshot_time or datetime.now().astimezone()
    result = run_market_sync(snapshot_time, config_dir=args.config_dir)
    if args.json_output:
        print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        print(f"task: {result.task}")
        print(f"status: {result.status.value}")
        print(f"snapshot_time: {result.snapshot_time}")
        print(f"expected: {result.expected}")
        print(f"actual: {result.actual}")
        print(f"missing: {result.missing}")
        for error in result.errors:
            print(f"error: {error}")
    return 1 if result.status.value == "failed" else 0


def _emit(results: Sequence[BaseModel], *, json_output: bool) -> None:
    if json_output:
        payload: list[dict[str, Any]] = [result.model_dump(mode="json") for result in results]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    for result in results:
        data = result.model_dump()
        print(f"{data['status'].upper():7} {data['name']}: {data['message']}")


def _parse_datetime(raw: str) -> datetime:
    try:
        return datetime.fromisoformat(raw)
    except ValueError as exc:
        msg = f"Invalid datetime: {raw}"
        raise argparse.ArgumentTypeError(msg) from exc


if __name__ == "__main__":
    raise SystemExit(main())
