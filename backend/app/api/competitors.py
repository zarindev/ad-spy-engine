from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app.analysis.scoring import badge_range
from app.api.serializers import competitor_out
from app.db.models import Ad, Competitor
from app.db.session import session_scope

router = APIRouter(prefix="/api/competitors", tags=["competitors"])


def _stats(session, competitor_id: int) -> dict:
    row = session.exec(
        select(
            func.count(Ad.id), func.avg(Ad.days_running), func.max(Ad.days_running), func.avg(Ad.score)
        ).where(Ad.competitor_id == competitor_id)
    ).one()
    active = session.exec(
        select(func.count(Ad.id)).where(Ad.competitor_id == competitor_id, Ad.status == "active")
    ).one()
    winners = session.exec(
        select(func.count(Ad.id)).where(
            Ad.competitor_id == competitor_id, Ad.score >= badge_range("winner")[0]
        )
    ).one()
    return {
        "ad_count": row[0] or 0,
        "active_ads": active or 0,
        "avg_days_running": round(row[1] or 0, 1),
        "max_days_running": row[2] or 0,
        "avg_score": round(row[3] or 0, 1),
        "winners": winners or 0,
    }


@router.get("")
def list_competitors() -> list[dict]:
    with session_scope() as session:
        comps = session.exec(select(Competitor).order_by(Competitor.last_scan_at.desc())).all()
        return [competitor_out(c, _stats(session, c.id)) for c in comps]


@router.get("/{competitor_id}")
def get_competitor(competitor_id: int) -> dict:
    with session_scope() as session:
        comp = session.get(Competitor, competitor_id)
        if comp is None:
            raise HTTPException(404, "Competitor not found")
        return competitor_out(comp, _stats(session, comp.id))
