from __future__ import annotations

from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Query
from sqlmodel import func, select

from app.api.serializers import ad_out, asset_url
from app.db.models import Ad, ChangeEvent, Competitor, utcnow
from app.db.session import session_scope

router = APIRouter(prefix="/api/changes", tags=["changes"])


@router.get("")
def list_changes(
    competitor_id: int | None = None,
    scan_id: int | None = None,
    kind: Literal["new", "stopped", "scaled"] | None = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
) -> dict:
    stmt = (
        select(ChangeEvent, Ad, Competitor)
        .join(Ad, Ad.id == ChangeEvent.ad_id)
        .join(Competitor, Competitor.id == ChangeEvent.competitor_id)
    )
    if competitor_id:
        stmt = stmt.where(ChangeEvent.competitor_id == competitor_id)
    if scan_id:
        stmt = stmt.where(ChangeEvent.scan_id == scan_id)
    if kind:
        stmt = stmt.where(ChangeEvent.kind == kind)
    with session_scope() as session:
        total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
        rows = session.exec(stmt.order_by(ChangeEvent.id.desc()).offset(offset).limit(limit)).all()
    return {
        "total": total,
        "items": [
            {
                "id": ev.id,
                "kind": ev.kind,
                "details": ev.details or {},
                "scan_id": ev.scan_id,
                "created_at": ev.created_at.isoformat(),
                "competitor_id": comp.id,
                "competitor_name": comp.name,
                "competitor_logo": asset_url(comp.logo_url),
                "ad": ad_out(ad),
            }
            for ev, ad, comp in rows
        ],
    }


@router.get("/summary")
def summary(days: int = 30, competitor_id: int | None = None) -> dict:
    since = utcnow() - timedelta(days=days)
    stmt = select(ChangeEvent.kind, func.count(ChangeEvent.id)).where(ChangeEvent.created_at >= since)
    if competitor_id:
        stmt = stmt.where(ChangeEvent.competitor_id == competitor_id)
    with session_scope() as session:
        counts = dict(session.exec(stmt.group_by(ChangeEvent.kind)).all())
    return {
        "days": days,
        "new": counts.get("new", 0),
        "stopped": counts.get("stopped", 0),
        "scaled": counts.get("scaled", 0),
    }
