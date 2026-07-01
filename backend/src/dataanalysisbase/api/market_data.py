"""Read-only market data API helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict

from dataanalysisbase.api.market_alerts import (
    MarketAlert,
    _market_alert_from_record,
    _refresh_persisted_alerts,
)
from dataanalysisbase.common.errors import StorageError
from dataanalysisbase.config_loader import load_settings
from dataanalysisbase.storage import (
    AggregateRepo,
    AlertRepo,
    DuckDBStore,
    IndustryQuery,
    StockQuery,
)
from dataanalysisbase.storage.repositories.page import Page


class MarketOverview(BaseModel):
    """Latest market overview aggregate."""

    model_config = ConfigDict(frozen=True)

    snapshot_time: str
    stock_count: int
    up_count: int
    down_count: int
    flat_count: int
    limit_up_count: int
    limit_down_count: int
    total_amount: float | None = None
    source: str


class StockItem(BaseModel):
    """Latest market snapshot row exposed to frontend tables."""

    model_config = ConfigDict(frozen=True)

    snapshot_time: str
    security_id: str
    name: str
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
    is_suspended: bool = False
    source: str
    fetched_at: str


class IndustryItem(BaseModel):
    """Latest industry aggregate row."""

    model_config = ConfigDict(frozen=True)

    snapshot_time: str
    industry_code: str
    stock_count: int
    change_pct_avg: float | None = None
    amount_sum: float | None = None
    up_count: int
    down_count: int
    source: str


class StockDetail(BaseModel):
    """Latest stock snapshot plus recent alert history."""

    model_config = ConfigDict(frozen=True)

    snapshot: StockItem
    alerts: list[MarketAlert]


def get_market_overview() -> MarketOverview:
    """Return latest market overview from DuckDB."""

    repo, store = _aggregate_repo()
    try:
        row = repo.get_overview()
    except StorageError as exc:
        raise _service_unavailable(exc) from exc
    finally:
        store.close()

    if row is None:
        raise HTTPException(status_code=404, detail="market overview is not available")
    return MarketOverview.model_validate(_jsonable_row(row))


def get_stocks_page(
    *,
    page: int = 1,
    size: int = 50,
    sort: str = "change_pct",
    order: Literal["asc", "desc"] = "desc",
    industry: str | None = None,
    q: str | None = None,
    filter: Literal["gainers", "losers", "limit_up", "limit_down", "volume"] | None = None,
) -> Page[StockItem]:
    """Return a page from the latest market snapshot table."""

    query = StockQuery(
        page=page,
        size=size,
        sort=sort,
        order=order,
        industry=industry,
        q=q,
        filter=filter,
    )
    repo, store = _aggregate_repo()
    try:
        result = repo.get_stocks_page(query)
    except StorageError as exc:
        raise _service_unavailable(exc) from exc
    finally:
        store.close()

    return Page[StockItem](
        items=[StockItem.model_validate(_jsonable_row(row)) for row in result.items],
        total=result.total,
        page=result.page,
        size=result.size,
    )


def get_stock_detail(security_id: str, *, alert_limit: int = 20) -> StockDetail:
    """Return the latest snapshot and alert history for one security."""

    settings = load_settings()
    repo, store = _aggregate_repo(settings.duckdb_path)
    try:
        row = repo.get_stock(security_id)
    except StorageError as exc:
        raise _service_unavailable(exc) from exc
    finally:
        store.close()

    if row is None:
        raise HTTPException(status_code=404, detail="stock not found in latest snapshot")

    _refresh_persisted_alerts(settings.duckdb_path, settings.config_dir)
    alert_repo, alert_store = _alert_repo(settings.duckdb_path, read_only=True)
    try:
        alerts = alert_repo.list_for_security(security_id, limit=alert_limit)
    except StorageError as exc:
        raise _service_unavailable(exc) from exc
    finally:
        alert_store.close()

    return StockDetail(
        snapshot=StockItem.model_validate(_jsonable_row(row)),
        alerts=[_market_alert_from_record(alert) for alert in alerts],
    )


def get_industries(
    *,
    limit: int = 50,
    sort: str = "change_pct_avg",
    order: Literal["asc", "desc"] = "desc",
) -> list[IndustryItem]:
    """Return latest industry aggregates."""

    query = IndustryQuery(limit=limit, sort=sort, order=order)
    repo, store = _aggregate_repo()
    try:
        rows = repo.get_industries(query)
    except StorageError as exc:
        raise _service_unavailable(exc) from exc
    finally:
        store.close()

    return [IndustryItem.model_validate(_jsonable_row(row)) for row in rows]


def _aggregate_repo(duckdb_path: Path | None = None) -> tuple[AggregateRepo, DuckDBStore]:
    if duckdb_path is None:
        duckdb_path = load_settings().duckdb_path
    store = DuckDBStore(duckdb_path, read_only=True)
    return AggregateRepo(store), store


def _alert_repo(duckdb_path: Path, *, read_only: bool = False) -> tuple[AlertRepo, DuckDBStore]:
    store = DuckDBStore(duckdb_path, read_only=read_only)
    return AlertRepo(store), store


def _jsonable_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value.isoformat() if hasattr(value, "isoformat") else value
        for key, value in row.items()
        if key != "created_at"
    }


def _service_unavailable(exc: StorageError) -> HTTPException:
    return HTTPException(status_code=503, detail=f"market data is not available: {exc}")
