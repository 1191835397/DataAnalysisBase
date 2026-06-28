"""FastAPI application entrypoint."""

from typing import Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Response, status

from dataanalysisbase import __version__
from dataanalysisbase.api.market_data import (
    IndustryItem,
    MarketOverview,
    StockItem,
    get_industries,
    get_market_overview,
    get_stocks_page,
)
from dataanalysisbase.api.sync_jobs import (
    MarketSyncAlreadyRunningError,
    MarketSyncJobStore,
)
from dataanalysisbase.config_loader import load_settings
from dataanalysisbase.delivery.sync import run_market_sync
from dataanalysisbase.domain.contracts import MarketSyncJobStatus
from dataanalysisbase.observability.system_status import RuntimeStatus, build_runtime_status
from dataanalysisbase.storage import DuckDBStore, SyncJobRepo
from dataanalysisbase.storage.repositories.page import Page

app = FastAPI(title="DataAnalysisBase API", version=__version__)


def _sync_job_repo() -> SyncJobRepo:
    settings = load_settings()
    store = DuckDBStore(settings.duckdb_path)
    store.init_schema()
    return SyncJobRepo(store)


_market_sync_jobs = MarketSyncJobStore(run_market_sync, job_store_factory=_sync_job_repo)


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


@app.post("/api/v1/sync/market", status_code=status.HTTP_202_ACCEPTED)
def start_market_sync(background_tasks: BackgroundTasks) -> MarketSyncJobStatus:
    """Start one whole-market sync job."""

    try:
        return _market_sync_jobs.start(background_tasks)
    except MarketSyncAlreadyRunningError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "market sync already running",
                "job_id": exc.job.job_id,
            },
        ) from exc


@app.get(
    "/api/v1/sync/market/latest",
    response_model=MarketSyncJobStatus,
    responses={204: {"description": "No API-triggered market sync job is available"}},
)
def latest_market_sync_status() -> MarketSyncJobStatus | Response:
    """Return the latest API-triggered market sync job status, if one exists."""

    job = _market_sync_jobs.latest()
    if job is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return job


@app.get("/api/v1/sync/market/jobs")
def market_sync_jobs(limit: int = Query(default=20, ge=1, le=100)) -> list[MarketSyncJobStatus]:
    """Return recent API-triggered market sync jobs."""

    return _market_sync_jobs.list_recent(limit)


@app.get("/api/v1/sync/market/{job_id}")
def market_sync_status(job_id: str) -> MarketSyncJobStatus:
    """Return one API-triggered market sync job status."""

    job = _market_sync_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="market sync job not found")
    return job


@app.post("/api/v1/sync/market/{job_id}/cancel")
def cancel_market_sync(job_id: str) -> MarketSyncJobStatus:
    """Request cancellation for one API-triggered market sync job."""

    job = _market_sync_jobs.request_cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="market sync job not found")
    return job


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
