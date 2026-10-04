from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app.analysis.ai import competitor_insights
from app.analysis.grouping import group_label, regroup_competitor
from app.analysis.scoring import badge_range
from app.api.serializers import ad_out, competitor_out, scan_out
from app.db.models import Ad, Competitor, Scan, utcnow
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


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


@router.get("/{competitor_id}/profile")
def competitor_profile(competitor_id: int, weeks: int = 26) -> dict:
    with session_scope() as session:
        comp = session.get(Competitor, competitor_id)
        if comp is None:
            raise HTTPException(404, "Competitor not found")
        ads = session.exec(select(Ad).where(Ad.competitor_id == competitor_id)).all()
        scans = session.exec(
            select(Scan).where(Scan.competitor_id == competitor_id).order_by(Scan.id.desc()).limit(6)
        ).all()
        insights = competitor_insights(session, competitor_id)
        stats = _stats(session, competitor_id)

    today = utcnow().date()
    first_week = _week_start(today - timedelta(weeks=weeks - 1))
    launches = Counter(_week_start(a.start_date) for a in ads if a.start_date and a.start_date >= first_week)
    timeline = []
    week = first_week
    while week <= today:
        active_then = sum(
            1
            for a in ads
            if a.start_date
            and a.start_date <= week + timedelta(days=6)
            and (a.status == "active" or (a.end_date and a.end_date >= week))
        )
        timeline.append({"week": week.isoformat(), "launched": launches.get(week, 0), "running": active_then})
        week += timedelta(weeks=1)

    buckets = [("≤ 7 days", 0, 7), ("8–30 days", 8, 30), ("31–90 days", 31, 90), ("90+ days", 91, 10**6)]
    groups: dict[str, list[Ad]] = defaultdict(list)
    for a in ads:
        if a.group_key and a.group_size > 1:
            groups[a.group_key].append(a)
    top_groups = sorted(groups.values(), key=lambda g: (-len(g), -max(x.score for x in g)))[:12]

    return {
        "competitor": competitor_out(comp, stats),
        "timeline": timeline,
        "formats": [{"name": k, "count": v} for k, v in Counter(a.media_type for a in ads).most_common()],
        "placements": [
            {"name": k, "count": v}
            for k, v in Counter(p for a in ads for p in a.platforms or []).most_common()
        ],
        "ctas": [
            {"name": k, "count": v} for k, v in Counter(a.cta_text for a in ads if a.cta_text).most_common(6)
        ],
        "longevity": [
            {"name": label, "count": sum(1 for a in ads if lo <= a.days_running <= hi)}
            for label, lo, hi in buckets
        ],
        "top_ads": [ad_out(a) for a in sorted(ads, key=lambda a: (-a.score, -a.days_running))[:8]],
        "groups": [
            {
                "key": g[0].group_key,
                "size": len(g),
                "creatives": g[0].group_creatives,
                "copies": g[0].group_copies,
                "label": group_label(g[0].group_creatives, g[0].group_copies),
                "best_score": max(x.score for x in g),
                "max_days": max(x.days_running for x in g),
                "lead": ad_out(max(g, key=lambda x: x.score)),
            }
            for g in top_groups
        ],
        "group_count": len(groups),
        "insights": insights,
        "recent_scans": [scan_out(s, comp) for s in scans],
    }


@router.post("/{competitor_id}/regroup")
def regroup(competitor_id: int) -> dict:
    with session_scope() as session:
        if session.get(Competitor, competitor_id) is None:
            raise HTTPException(404, "Competitor not found")
        result = regroup_competitor(session, competitor_id)
        session.commit()
    return result
