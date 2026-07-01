"""Cross-module DTOs."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from dataanalysisbase.domain.enums import AlertSeverity, AlertStatus, DatasetType, RunStatus


class RawDataset(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    dataset_type: DatasetType
    fetched_at: datetime
    records: list[dict[str, Any]]
    raw_hash: str
    security_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MarketRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot_time: datetime
    security_id: str
    name: str
    source: str
    fetched_at: datetime
    price: float | None = None
    change_pct: float | None = None
    volume: float | None = None
    amount: float | None = None
    turnover_rate: float | None = None
    volume_ratio: float | None = None
    pe_ttm: float | None = None
    pb: float | None = None
    market_cap: float | None = None
    industry_code: str | None = None
    listing_date: date | None = None
    ex_dividend: bool = False
    is_suspended: bool = False


class SyncLogEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    at: datetime
    stage: str
    level: str = "info"
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class SyncResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    task: str
    status: RunStatus
    expected: int
    actual: int
    missing: int
    snapshot_time: datetime | None = None
    errors: list[str] = Field(default_factory=list)
    logs: list[SyncLogEntry] = Field(default_factory=list)


class MarketSyncJobStatus(BaseModel):
    """Observable state for one API-triggered market sync job."""

    job_id: str
    status: RunStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: SyncResult | None = None
    error: str | None = None
    cancel_requested: bool = False
    elapsed_seconds: int = 0
    message: str = "正在抓取 AKShare 全市场快照"
    artifact_path: str | None = None


class SurveillanceAlertRecord(BaseModel):
    """Persisted market surveillance alert with lifecycle metadata."""

    alert_id: str
    rule_id: str | None = None
    severity: AlertSeverity
    kind: str
    status: AlertStatus = AlertStatus.NEW
    title: str
    message: str
    first_triggered_at: datetime
    last_triggered_at: datetime
    trigger_count: int = 1
    security_id: str | None = None
    name: str | None = None
    industry_code: str | None = None
    metric: str | None = None
    value: float | None = None
    threshold: float | None = None
    snapshot_time: datetime | None = None
    source: str | None = None


class FusionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    security_id: str
    canonical_counts: dict[str, int]
    issues: list[str] = Field(default_factory=list)
    blocked: bool = False
