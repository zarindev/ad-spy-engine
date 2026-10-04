from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from app.analysis import ai
from app.core.config import ai_model
from app.core.demo import require_live
from app.db.models import AiRun
from app.db.session import session_scope
from app.jobs.ai_worker import ai_worker, resolve_scope

router = APIRouter(prefix="/api/ai", tags=["ai"])


class Scope(BaseModel):
    ad_ids: list[int] | None = None
    scan_id: int | None = None
    competitor_id: int | None = None
    only_winners: bool = False
    limit: int = Field(100, ge=1, le=2000)


def run_out(run: AiRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "status": run.status,
        "model": run.model,
        "scope": run.scope,
        "total": run.total,
        "done": run.done,
        "failed": run.failed,
        "cached": run.cached,
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "cost_usd": run.cost_usd,
        "estimate_usd": run.estimate_usd,
        "error": run.error,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


@router.get("/status")
def status() -> dict:
    return {"enabled": ai.is_enabled(), "model": ai_model()}


@router.post("/estimate")
def estimate(scope: Scope) -> dict:
    with session_scope() as session:
        return ai.estimate(session, resolve_scope(session, scope.model_dump()))


@router.post("/runs", status_code=201)
def start_run(scope: Scope) -> dict:
    require_live()
    try:
        run = ai_worker.start(scope.model_dump())
    except ai.AIDisabled as exc:
        raise HTTPException(400, str(exc)) from exc
    return run_out(run)


@router.get("/runs")
def list_runs(limit: int = 20) -> list[dict]:
    with session_scope() as session:
        return [run_out(r) for r in session.exec(select(AiRun).order_by(AiRun.id.desc()).limit(limit)).all()]


@router.get("/runs/{run_id}")
def get_run(run_id: int) -> dict:
    with session_scope() as session:
        run = session.get(AiRun, run_id)
        if run is None:
            raise HTTPException(404, "Run not found")
        return run_out(run)


@router.get("/insights/{competitor_id}")
def insights(competitor_id: int) -> dict:
    with session_scope() as session:
        return ai.competitor_insights(session, competitor_id)
