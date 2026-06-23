"""FastAPI application entrypoint."""

from fastapi import FastAPI

from dataanalysisbase import __version__

app = FastAPI(title="DataAnalysisBase API", version=__version__)


@app.get("/health")
def health() -> dict[str, str]:
    """Return a minimal process health response."""

    return {"status": "ok", "version": __version__}


@app.get("/api/v1/health")
def api_health() -> dict[str, str]:
    """Return API health under the versioned prefix used by the frontend."""

    return health()
