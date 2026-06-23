"""Sync schedule and surveillance rule configuration models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dataanalysisbase.domain.enums import AlertSeverity


class TradingSession(BaseModel):
    model_config = ConfigDict(frozen=True)

    start: str
    end: str


class JobConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    description: str = ""
    interval_minutes: int | None = Field(default=None, gt=0)
    cron: str | None = None
    trading_sessions: list[TradingSession] = Field(default_factory=list)
    trading_days_only: bool = True
    on_complete: str | None = None

    @model_validator(mode="after")
    def require_schedule(self) -> "JobConfig":
        if self.interval_minutes is None and self.cron is None:
            raise ValueError("job needs interval_minutes or cron")
        return self


class SyncSchedule(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str
    timezone: str = "Asia/Shanghai"
    jobs: dict[str, JobConfig]


class Condition(BaseModel):
    model_config = ConfigDict(frozen=True)

    field: str
    op: Literal["gte", "lte", "gt", "lt", "eq", "abs_gte"]
    value: float


class RuleConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str
    scope: Literal["market", "industry", "focus"]
    severity: AlertSeverity
    condition: Condition
    enabled: bool = True
    version: str = "1.0"
    cooldown_minutes: int = Field(default=30, gt=0)
    explanation_template: str | None = None


class DedupeConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    window_minutes: int = Field(default=30, gt=0)


class SurveillanceRules(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str
    dedupe: DedupeConfig = Field(default_factory=DedupeConfig)
    rules: dict[str, RuleConfig]
