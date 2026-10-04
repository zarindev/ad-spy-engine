"""FastAPI application: REST API + SSE + static media + the built React frontend."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    ads,
    ai,
    boards,
    changes,
    clients,
    compare,
    competitors,
    events,
    reports,
    scans,
    settings,
    stats,
    watchlist,
)
from app.core.demo import is_demo
from app.core.logging import setup_logging
from app.core.paths import FRONTEND_DIST, media_dir, reports_dir
from app.db.session import run_migrations
from app.jobs.ai_worker import ai_worker
from app.jobs.scheduler import scheduler
from app.jobs.worker import worker
from app.scraper.cleanup import cleanup_orphans

log = logging.getLogger(__name__)
VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    run_migrations()
    cleanup_orphans()
    ai_worker.recover()
    recovered = worker.recover()
    if any(recovered.values()):
        log.warning("Startup recovery: %s", recovered)
    if not is_demo():
        scheduler.start()
    log.info("Ad Spy Engine %s started", VERSION)
    yield
    scheduler.shutdown()
    ai_worker.shutdown()
    worker.shutdown()


app = FastAPI(
    title="Ad Spy Engine",
    version=VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (
    scans,
    ads,
    competitors,
    clients,
    compare,
    boards,
    stats,
    reports,
    settings,
    events,
    ai,
    watchlist,
    changes,
):
    app.include_router(module.router)

# Only media and reports are exposed — never the database or logs.
app.mount("/files/media", StaticFiles(directory=media_dir()), name="media")
app.mount("/files/reports", StaticFiles(directory=reports_dir()), name="reports")


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "version": VERSION,
        "demo": is_demo(),
        "frontend_built": (FRONTEND_DIST / "index.html").exists(),
    }


@app.exception_handler(Exception)
async def unhandled(_request: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled API error")
    return JSONResponse({"detail": f"Internal error: {type(exc).__name__}"}, status_code=500)


if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    """Serve the built single-page app; unknown paths fall back to index.html."""
    if path.startswith(("api/", "files/")):
        raise HTTPException(404)
    candidate = (FRONTEND_DIST / path).resolve()
    if path and candidate.is_file() and FRONTEND_DIST.resolve() in candidate.parents:
        return FileResponse(candidate)
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse(
        {"detail": "Frontend not built. Run setup (npm run build) or use the Vite dev server on :5173."},
        status_code=503,
    )
