"""Local industry mapping file loader."""

from __future__ import annotations

import csv
import json
from pathlib import Path


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
