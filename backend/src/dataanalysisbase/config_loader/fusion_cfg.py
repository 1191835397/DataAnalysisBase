"""Fusion and reconciliation configuration models."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DatasetFusionPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy: str
    trusted_source: str | None = None
    fallback_source: str | None = None
    min_sources: int | None = Field(default=None, gt=0)
    diff_threshold: dict[str, float] = Field(default_factory=dict)
    dedupe: dict[str, Any] = Field(default_factory=dict)
    max_items_per_security: int | None = Field(default=None, gt=0)


class FusionPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str
    datasets: dict[str, DatasetFusionPolicy]


class SeverityLevelPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    description: str
    action: str
    block_research: bool = False
    downgrade_confidence: float | None = None
    alert: bool = False


class ReconcileThresholds(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str
    severity_levels: dict[str, SeverityLevelPolicy]
    field_defaults: dict[str, dict[str, float]]
