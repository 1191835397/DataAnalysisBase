"""Cross-module DTOs."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from dataanalysisbase.domain.enums import DatasetType, RunStatus


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


class SyncResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    task: str
    status: RunStatus
    expected: int
    actual: int
    missing: int
    snapshot_time: datetime | None = None
    errors: list[str] = Field(default_factory=list)


class FusionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    security_id: str
    canonical_counts: dict[str, int]
    issues: list[str] = Field(default_factory=list)
    blocked: bool = False
