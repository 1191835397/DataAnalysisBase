"""Config file loading helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from dataanalysisbase.common.errors import ConfigError
from dataanalysisbase.config_loader.fusion_cfg import FusionPolicy, ReconcileThresholds
from dataanalysisbase.config_loader.providers_cfg import ProvidersConfig
from dataanalysisbase.config_loader.settings import Settings
from dataanalysisbase.config_loader.surveillance_cfg import SurveillanceRules, SyncSchedule
from dataanalysisbase.config_loader.watchlist_cfg import Watchlist

T = TypeVar("T", bound=BaseModel)


def load_settings() -> Settings:
    try:
        settings = Settings()
    except ValidationError as exc:
        raise ConfigError(f"Invalid environment settings: {exc}") from exc
    return _resolve_settings_paths(settings)


def load_providers(config_dir: Path | None = None) -> ProvidersConfig:
    return _load_model("providers.yaml", ProvidersConfig, config_dir=config_dir)


def load_sync_schedule(config_dir: Path | None = None) -> SyncSchedule:
    return _load_model("sync_schedule.yaml", SyncSchedule, config_dir=config_dir)


def load_surveillance_rules(config_dir: Path | None = None) -> SurveillanceRules:
    raw = _load_yaml("surveillance_rules.yaml", config_dir=config_dir)
    rules = raw.get("rules")
    if not isinstance(rules, dict):
        raise ConfigError("surveillance_rules.yaml must contain a rules mapping.")

    raw["rules"] = {
        rule_id: {"rule_id": rule_id, **rule_config}
        for rule_id, rule_config in rules.items()
        if isinstance(rule_config, dict)
    }
    return _validate(raw, SurveillanceRules, "surveillance_rules.yaml")


def load_watchlist(config_dir: Path | None = None) -> Watchlist:
    return _load_model("watchlist.yaml", Watchlist, config_dir=config_dir)


def load_fusion_policy(config_dir: Path | None = None) -> FusionPolicy:
    return _load_model("fusion_policy.yaml", FusionPolicy, config_dir=config_dir)


def load_reconcile_thresholds(config_dir: Path | None = None) -> ReconcileThresholds:
    return _load_model("reconcile_thresholds.yaml", ReconcileThresholds, config_dir=config_dir)


def _config_dir(config_dir: Path | None = None) -> Path:
    return config_dir if config_dir is not None else load_settings().config_dir


def _resolve_settings_paths(settings: Settings) -> Settings:
    root = _project_root()
    return settings.model_copy(
        update={
            "config_dir": _resolve_project_path(root, settings.config_dir),
            "data_dir": _resolve_project_path(root, settings.data_dir),
            "duckdb_path": _resolve_project_path(root, settings.duckdb_path),
            "chroma_dir": _resolve_project_path(root, settings.chroma_dir),
        }
    )


def _resolve_project_path(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _project_root() -> Path:
    for path in (Path.cwd(), *Path.cwd().parents):
        if (path / "backend").is_dir() and (path / "config").is_dir():
            return path
    return Path.cwd()


def _load_model(filename: str, model: type[T], *, config_dir: Path | None = None) -> T:
    return _validate(_load_yaml(filename, config_dir=config_dir), model, filename)


def _load_yaml(filename: str, *, config_dir: Path | None = None) -> dict[str, Any]:
    path = _config_dir(config_dir) / filename
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except OSError as exc:
        raise ConfigError(f"Failed to read config file {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"Config file must contain a mapping: {path}")
    return data


def _validate(data: dict[str, Any], model: type[T], filename: str) -> T:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"Invalid config {filename}: {exc}") from exc
