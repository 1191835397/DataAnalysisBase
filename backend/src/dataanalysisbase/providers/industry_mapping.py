"""Local industry mapping file loader."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from dataanalysisbase.common.errors import InvalidSecurityId
from dataanalysisbase.domain.symbols import SecurityId


class IndustryMappingProvider(Protocol):
    """Provider protocol for security-to-industry mapping sync."""

    name: str

    def fetch_industry_mapping(self) -> dict[str, str]:
        """Fetch security-to-industry mapping records."""


class IndustryMappingSyncResult(BaseModel):
    """Result of writing a local industry mapping file."""

    model_config = ConfigDict(frozen=True)

    task: str = "industry_mapping_sync"
    status: str
    source: str
    path: str
    records: int
    errors: list[str] = []


class IndustryMappingBackfillResult(BaseModel):
    """Result of applying a local industry mapping to market snapshots."""

    model_config = ConfigDict(frozen=True)

    task: str = "industry_mapping_backfill"
    status: str
    path: str
    snapshot_time: str | None
    mapping_records: int
    backfilled: int
    errors: list[str] = []


class IndustryMappingCoverageResult(BaseModel):
    """Coverage audit for the latest market snapshot and local mapping file."""

    model_config = ConfigDict(frozen=True)

    task: str = "industry_mapping_coverage"
    status: str
    path: str
    snapshot_time: str | None
    total_snapshot_records: int
    mapped_snapshot_records: int
    unknown_snapshot_records: int
    mapping_records: int
    usable_mapping_records: int
    missing_mapping_records: int
    coverage_ratio: float
    missing_output: str | None = None
    errors: list[str] = []


def load_industry_mapping_file(path: Path) -> list[dict[str, object]]:
    """Load a local industry mapping file as normalized record dictionaries."""

    if path.suffix.lower() == ".csv":
        return _load_csv(path)
    if path.suffix.lower() == ".json":
        return _load_json(path)
    msg = f"Unsupported industry mapping file type: {path.suffix}"
    raise ValueError(msg)


def _load_csv(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _load_json(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    if isinstance(raw, dict):
        return [
            {"security_id": security_id, "industry": industry}
            for security_id, industry in raw.items()
        ]
    if isinstance(raw, list):
        return [record for record in raw if isinstance(record, dict)]

    msg = "Industry mapping JSON must be an object or an array of objects"
    raise ValueError(msg)


def write_industry_mapping_csv(path: Path, mapping: dict[str, str]) -> int:
    """Write a security-to-industry mapping as a stable CSV file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["security_id", "industry"])
        writer.writeheader()
        for security_id, industry in sorted(mapping.items()):
            writer.writerow({"security_id": security_id, "industry": industry})
    return len(mapping)


def write_missing_industry_mapping_csv(
    path: Path,
    rows: list[dict[str, str]],
) -> int:
    """Write a stable CSV template for securities missing industry mapping."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["security_id", "name", "industry"])
        writer.writeheader()
        for row in sorted(rows, key=lambda item: item["security_id"]):
            writer.writerow(
                {
                    "security_id": row["security_id"],
                    "name": row["name"],
                    "industry": row.get("industry", ""),
                }
            )
    return len(rows)


def normalize_security_id(raw: object) -> str | None:
    """Normalize a provider/file security identifier to SYMBOL.MARKET when possible."""

    if raw is None:
        return None
    try:
        return str(SecurityId.parse(str(raw)))
    except InvalidSecurityId:
        return None
