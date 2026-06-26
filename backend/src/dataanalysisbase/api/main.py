"""FastAPI application entrypoint."""

from typing import Literal

from fastapi import FastAPI, Query

from dataanalysisbase import __version__
from dataanalysisbase.api.market_data import (
    IndustryItem,
    MarketOverview,
    StockItem,
    get_industries,
    get_market_overview,
    get_stocks_page,
)
from dataanalysisbase.observability.system_status import RuntimeStatus, build_runtime_status
from dataanalysisbase.storage.repositories.page import Page

app = FastAPI(title="DataAnalysisBase API", version=__version__)


@app.get("/health")
def health() -> dict[str, str]:
    """Return a minimal process health response."""

    return {"status": "ok", "version": __version__}


@app.get("/api/v1/health")
def api_health() -> dict[str, str]:
    """Return API health under the versioned prefix used by the frontend."""

    return health()


@app.get("/api/v1/system/status")
def system_status(online: bool = False) -> RuntimeStatus:
    """Return compact runtime status for diagnostics and UI status panels."""

    return build_runtime_status(include_online=online)


@app.get("/api/v1/market/overview")
def market_overview() -> MarketOverview:
    """Return the latest market overview aggregate."""

    return get_market_overview()


@app.get("/api/v1/stocks")
def stocks(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    sort: str = "change_pct",
    order: Literal["asc", "desc"] = "desc",
    industry: str | None = None,
    q: str | None = None,
    filter: Literal["gainers", "losers", "limit_up", "limit_down", "volume"] | None = None,
) -> Page[StockItem]:
    """Return a page from the latest market snapshot."""

    return get_stocks_page(
        page=page,
        size=size,
        sort=sort,
        order=order,
        industry=industry,
        q=q,
        filter=filter,
    )


@app.get("/api/v1/industries")
def industries(
    limit: int = Query(default=50, ge=1, le=200),
    sort: str = "change_pct_avg",
    order: Literal["asc", "desc"] = "desc",
) -> list[IndustryItem]:
    """Return latest industry aggregates."""

    return get_industries(limit=limit, sort=sort, order=order)


@app.get("/api/v1/industries/{industry_code}/stocks")
def industry_stocks(
    industry_code: str,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    sort: str = "change_pct",
    order: Literal["asc", "desc"] = "desc",
    filter: Literal["gainers", "losers", "limit_up", "limit_down", "volume"] | None = None,
) -> Page[StockItem]:
    """Return stocks from the latest snapshot for one industry."""

    return get_stocks_page(
        page=page,
        size=size,
        sort=sort,
        order=order,
        industry=industry_code,
        filter=filter,
    )
