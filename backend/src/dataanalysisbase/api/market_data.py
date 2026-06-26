"""Read-only market data API helpers."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict

from dataanalysisbase.common.errors import StorageError
from dataanalysisbase.config_loader import load_settings
from dataanalysisbase.storage import AggregateRepo, DuckDBStore, StockQuery
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
    source: str
    fetched_at: str


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


def _aggregate_repo() -> tuple[AggregateRepo, DuckDBStore]:
    settings = load_settings()
    store = DuckDBStore(settings.duckdb_path, read_only=True)
    return AggregateRepo(store), store


def _jsonable_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value.isoformat() if hasattr(value, "isoformat") else value
        for key, value in row.items()
        if key != "created_at"
    }


def _service_unavailable(exc: StorageError) -> HTTPException:
    return HTTPException(status_code=503, detail=f"market data is not available: {exc}")
