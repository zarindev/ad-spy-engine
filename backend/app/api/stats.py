from __future__ import annotations

from collections import Counter
from datetime import timedelta

from fastapi import APIRouter
from sqlmodel import func, select

from app.analysis.scoring import badge_for, badge_range
from app.api.serializers import scan_out
from app.db.models import Ad, Competitor, Scan, ScanStatus, utcnow
from app.db.session import session_scope

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/dashboard")
def dashboard() -> dict:
    now = utcnow()
    week_ago = now - timedelta(days=7)
    with session_scope() as session:
        ads_tracked = session.exec(select(func.count(Ad.id))).one()
        active_ads = session.exec(select(func.count(Ad.id)).where(Ad.status == "active")).one()
        winners = session.exec(select(func.count(Ad.id)).where(Ad.score >= badge_range("winner")[0])).one()
        new_week = session.exec(select(func.count(Ad.id)).where(Ad.first_seen_at >= week_ago)).one()
        competitors = session.exec(select(func.count(Competitor.id))).one()
        active_scans = session.exec(
            select(func.count(Scan.id)).where(Scan.status.in_([ScanStatus.QUEUED, ScanStatus.RUNNING]))
        ).one()
        recent = session.exec(
            select(Scan, Competitor)
            .join(Competitor, Competitor.id == Scan.competitor_id)
            .order_by(Scan.id.desc())
            .limit(8)
        ).all()
        completed = session.exec(
            select(Scan)
            .where(Scan.status == ScanStatus.COMPLETED, Scan.ads_found >= 20)
            .order_by(Scan.id.desc())
            .limit(10)
        ).all()
        fourteen = now - timedelta(days=13)
        seen = session.exec(select(Ad.first_seen_at).where(Ad.first_seen_at >= fourteen)).all()
        formats = session.exec(select(Ad.media_type, func.count(Ad.id)).group_by(Ad.media_type)).all()
        scores = session.exec(select(Ad.score)).all()

    rates = [s.ads_found / s.duration_seconds * 60 for s in completed if s.duration_seconds]
    per_day = Counter(d.date().isoformat() for d in seen)
    days = [(now - timedelta(days=i)).date().isoformat() for i in range(13, -1, -1)]
    badges = Counter(badge_for(s) for s in scores)
    return {
        "kpis": {
            "ads_tracked": ads_tracked,
            "active_ads": active_ads,
            "winners": winners,
            "new_this_week": new_week,
            "competitors": competitors,
            "active_scans": active_scans,
        },
        "recent_scans": [scan_out(s, c) for s, c in recent],
        "ads_per_day": [{"date": d, "count": per_day.get(d, 0)} for d in days],
        "formats": [{"name": n, "count": c} for n, c in sorted(formats, key=lambda x: -x[1])],
        "badges": [{"name": b, "count": badges.get(b, 0)} for b in ("winner", "promising", "testing")],
        "avg_ads_per_minute": round(sum(rates) / len(rates), 1) if rates else None,
        "activity": [
            {
                "scan_id": s.id,
                "competitor_id": c.id,
                "competitor_name": c.name,
                "status": s.status,
                "new_ads": s.new_ads,
                "ads_found": s.ads_found,
                "at": (s.finished_at or s.created_at).isoformat(),
            }
            for s, c in recent
        ],
    }
