"""Local industry mapping file loader."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict


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
