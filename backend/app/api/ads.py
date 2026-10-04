from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy import String, cast, or_
from sqlmodel import func, select

from app.analysis.ai import analysis_out
from app.analysis.grouping import group_label
from app.analysis.scoring import badge_range
from app.api.scans import ads_to_csv
from app.api.serializers import ad_out, landing_out
from app.core.demo import require_live
from app.db.models import Ad, AdAnalysis, AdSnapshot, Competitor, Scan
from app.db.session import session_scope
from app.scraper.landing import capture_landing_pages, is_capturable, landing_for

router = APIRouter(prefix="/api/ads", tags=["ads"])

SORTS = {
    "score": (Ad.score.desc(), Ad.days_running.desc()),
    "days": (Ad.days_running.desc(), Ad.score.desc()),
    "newest": (Ad.start_date.desc(), Ad.score.desc()),
    "variations": (Ad.variation_count.desc(), Ad.score.desc()),
    "first_seen": (Ad.first_seen_at.desc(),),
}


def build_query(
    scan_id: int | None,
    competitor_id: int | None,
    q: str | None,
    badge: str | None,
    media_type: str | None,
    platform: str | None,
    status: str | None,
    ids: str | None = None,
):
    stmt = select(Ad)
    if scan_id:
        stmt = stmt.join(AdSnapshot, AdSnapshot.ad_id == Ad.id).where(AdSnapshot.scan_id == scan_id)
    if competitor_id:
        stmt = stmt.where(Ad.competitor_id == competitor_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Ad.ad_copy.ilike(like),
                Ad.headline.ilike(like),
                Ad.page_name.ilike(like),
                Ad.description.ilike(like),
                Ad.library_id == q.strip(),
            )
        )
    if badge:
        low, high = badge_range(badge)
        stmt = stmt.where(Ad.score >= low, Ad.score <= high)
    if media_type:
        stmt = stmt.where(Ad.media_type.in_(media_type.split(",")))
    if platform:
        for p in platform.upper().split(","):
            stmt = stmt.where(cast(Ad.platforms, String).like(f'%"{p}"%'))
    if status:
        stmt = stmt.where(Ad.status == status)
    if ids:
        stmt = stmt.where(Ad.id.in_([int(i) for i in ids.split(",") if i.isdigit()]))
    return stmt


def _dedupe_groups(session, stmt, sort: str, limit: int, offset: int) -> tuple[list[Ad], int]:
    """One ad per variation group (the first by the chosen sort), then paginate."""
    rows = session.execute(stmt.with_only_columns(Ad.id, Ad.group_key).order_by(*SORTS[sort])).all()
    seen: set[str] = set()
    ids: list[int] = []
    for ad_id, key in rows:
        k = key or f"solo-{ad_id}"
        if k in seen:
            continue
        seen.add(k)
        ids.append(ad_id)
    page_ids = ids[offset : offset + limit]
    ads = {a.id: a for a in session.exec(select(Ad).where(Ad.id.in_(page_ids))).all()} if page_ids else {}
    return [ads[i] for i in page_ids if i in ads], len(ids)


@router.get("")
def list_ads(
    scan_id: int | None = None,
    competitor_id: int | None = None,
    q: str | None = None,
    badge: Literal["winner", "promising", "testing"] | None = None,
    media_type: str | None = None,
    platform: str | None = None,
    status: Literal["active", "inactive"] | None = None,
    sort: Literal["score", "days", "newest", "variations", "first_seen"] = "score",
    group_key: str | None = None,
    grouped: bool = False,
    limit: int = Query(60, le=500),
    offset: int = 0,
) -> dict:
    stmt = build_query(scan_id, competitor_id, q, badge, media_type, platform, status)
    if group_key:
        stmt = stmt.where(Ad.group_key == group_key)
    with session_scope() as session:
        if grouped:
            ads, total = _dedupe_groups(session, stmt, sort, limit, offset)
        else:
            total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
            ads = session.exec(stmt.order_by(*SORTS[sort]).offset(offset).limit(limit)).all()
    return {"items": [ad_out(a) for a in ads], "total": total}


@router.get("/export.csv")
def export_csv(
    scan_id: int | None = None,
    competitor_id: int | None = None,
    q: str | None = None,
    badge: str | None = None,
    media_type: str | None = None,
    platform: str | None = None,
    status: str | None = None,
    ids: str | None = None,
) -> StreamingResponse:
    stmt = build_query(scan_id, competitor_id, q, badge, media_type, platform, status, ids)
    with session_scope() as session:
        ads = session.exec(stmt.order_by(Ad.score.desc())).all()
    return StreamingResponse(
        iter([ads_to_csv(list(ads))]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ad-spy-export.csv"'},
    )


@router.get("/{ad_id}")
def get_ad(ad_id: int) -> dict:
    with session_scope() as session:
        ad = session.get(Ad, ad_id)
        if ad is None:
            raise HTTPException(404, "Ad not found")
        history = session.exec(
            select(AdSnapshot, Scan)
            .join(Scan, Scan.id == AdSnapshot.scan_id)
            .where(AdSnapshot.ad_id == ad_id)
            .order_by(AdSnapshot.captured_at)
        ).all()
        group: list[Ad] = []
        if ad.group_key and ad.group_size > 1:
            group = session.exec(
                select(Ad)
                .where(Ad.group_key == ad.group_key, Ad.id != ad.id)
                .order_by(Ad.score.desc())
                .limit(24)
            ).all()
        landing = landing_for(session, ad.landing_url)
        analysis = session.exec(select(AdAnalysis).where(AdAnalysis.library_id == ad.library_id)).first()
    data = ad_out(ad, detail=True)
    data["group"] = {
        "key": ad.group_key,
        "size": ad.group_size,
        "creatives": ad.group_creatives,
        "copies": ad.group_copies,
        "label": group_label(ad.group_creatives, ad.group_copies),
        "members": [ad_out(g) for g in group],
    }
    data["landing_page"] = landing_out(landing)
    data["landing_capturable"] = is_capturable(ad.landing_url)
    data["analysis"] = analysis_out(analysis)
    data["history"] = [
        {
            "scan_id": s.scan_id,
            "captured_at": s.captured_at.isoformat(),
            "status": s.status,
            "variation_count": s.variation_count,
            "days_running": s.days_running,
            "score": s.score,
        }
        for s, _ in history
    ]
    return data


def _capture_landing(ad_id: int) -> dict:
    with session_scope() as session:
        ad = session.get(Ad, ad_id)
        if ad is None:
            raise HTTPException(404, "Ad not found")
        if not is_capturable(ad.landing_url):
            raise HTTPException(422, "This ad has no capturable external landing page")
        competitor = session.get(Competitor, ad.competitor_id)
        capture_landing_pages(
            session, [ad.landing_url], competitor.slug if competitor else "misc", max_age_days=0
        )
        return landing_out(landing_for(session, ad.landing_url)) or {}


@router.post("/{ad_id}/landing")
async def capture_landing(ad_id: int) -> dict:
    require_live()
    return await run_in_threadpool(_capture_landing, ad_id)
