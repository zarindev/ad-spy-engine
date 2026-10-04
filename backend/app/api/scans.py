from __future__ import annotations

import csv
import io
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import func, select

from app.api.serializers import library_url, scan_out
from app.core.config import get_settings
from app.core.demo import require_live
from app.core.paths import slugify
from app.db.models import Ad, AdSnapshot, Competitor, Scan, ScanStatus
from app.db.session import session_scope
from app.jobs.runner import create_scan
from app.jobs.worker import worker
from app.scraper.ad_library import ScanParams, build_search_url

router = APIRouter(prefix="/api/scans", tags=["scans"])


class ScanCreate(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    search_type: Literal["keyword", "page_id"] = "keyword"
    competitor_name: str | None = None
    country: str = "US"
    media_type: Literal["all", "image", "video", "meme", "carousel"] = "all"
    platforms: list[str] = []
    active_status: Literal["active", "inactive", "all"] = "active"
    max_ads: int = Field(200, ge=1, le=5000)
    exact_page: bool = False
    headless: bool | None = None


@router.post("", status_code=201)
def start_scan(body: ScanCreate) -> dict:
    require_live()
    if body.search_type == "page_id" and not body.query.strip().isdigit():
        raise HTTPException(422, "A Page ID must contain digits only.")
    headless = body.headless
    if headless is None:
        headless = bool(get_settings().get("scraping", {}).get("headless", True))
    params = ScanParams(
        query=body.query.strip(),
        search_type=body.search_type,
        country=body.country,
        media_type=body.media_type,
        platforms=body.platforms,
        active_status=body.active_status,
        max_ads=body.max_ads,
        exact_page=body.exact_page,
        headless=headless,
    )
    scan = create_scan(params, competitor_name=(body.competitor_name or "").strip() or None)
    worker.enqueue(scan.id)
    return scan_out(scan)


@router.get("/preview-url")
def preview_url(
    query: str,
    search_type: str = "keyword",
    country: str = "US",
    media_type: str = "all",
    platforms: str = "",
) -> dict:
    params = ScanParams(
        query=query,
        search_type=search_type,
        country=country,
        media_type=media_type,
        platforms=[p for p in platforms.split(",") if p],
    )
    return {"url": build_search_url(params)}


@router.get("")
def list_scans(
    limit: int = Query(50, le=500),
    offset: int = 0,
    competitor_id: int | None = None,
    status: str | None = None,
) -> dict:
    with session_scope() as session:
        stmt = select(Scan, Competitor).join(Competitor, Competitor.id == Scan.competitor_id)
        count = select(func.count()).select_from(Scan)
        if competitor_id:
            stmt = stmt.where(Scan.competitor_id == competitor_id)
            count = count.where(Scan.competitor_id == competitor_id)
        if status:
            stmt = stmt.where(Scan.status == status)
            count = count.where(Scan.status == status)
        rows = session.exec(stmt.order_by(Scan.id.desc()).offset(offset).limit(limit)).all()
        total = session.exec(count).one()
    return {"items": [scan_out(s, c) for s, c in rows], "total": total}


@router.get("/active")
def active_scans() -> list[dict]:
    with session_scope() as session:
        rows = session.exec(
            select(Scan, Competitor)
            .join(Competitor, Competitor.id == Scan.competitor_id)
            .where(Scan.status.in_([ScanStatus.QUEUED, ScanStatus.RUNNING]))
            .order_by(Scan.id)
        ).all()
    return [scan_out(s, c) for s, c in rows]


def _get(scan_id: int) -> tuple[Scan, Competitor | None]:
    with session_scope() as session:
        scan = session.get(Scan, scan_id)
        if scan is None:
            raise HTTPException(404, "Scan not found")
        return scan, session.get(Competitor, scan.competitor_id)


@router.get("/{scan_id}")
def get_scan(scan_id: int) -> dict:
    scan, comp = _get(scan_id)
    return scan_out(scan, comp)


@router.post("/{scan_id}/cancel")
def cancel_scan(scan_id: int) -> dict:
    scan, comp = _get(scan_id)
    if scan.status in ScanStatus.FINISHED:
        raise HTTPException(409, f"Scan already {scan.status}")
    if not worker.cancel(scan_id):
        raise HTTPException(409, "Scan is not running in this app instance")
    return {"ok": True}


@router.post("/{scan_id}/rerun", status_code=201)
def rerun_scan(scan_id: int) -> dict:
    require_live()
    old, comp = _get(scan_id)
    body = ScanCreate(
        query=old.query,
        search_type=old.search_type,
        country=old.country,
        media_type=old.media_type,
        platforms=old.platforms or [],
        active_status=old.active_status,
        max_ads=old.max_ads,
        exact_page=old.exact_page,
        headless=old.headless,
        competitor_name=comp.name if comp else None,
    )
    return start_scan(body)


@router.get("/{scan_id}/log", response_class=PlainTextResponse)
def scan_log(scan_id: int, tail: int = Query(500, le=20000)) -> str:
    scan, _ = _get(scan_id)
    if not scan.log_path:
        return ""
    from pathlib import Path

    path = Path(scan.log_path)
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-tail:])


CSV_FIELDS = [
    "library_id",
    "page_name",
    "page_id",
    "status",
    "score",
    "badge",
    "days_running",
    "start_date",
    "end_date",
    "media_type",
    "variation_count",
    "platforms",
    "headline",
    "ad_copy",
    "description",
    "cta_text",
    "landing_url",
    "library_url",
    "first_seen_at",
    "last_seen_at",
]


def ads_to_csv(ads: list[Ad]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for ad in ads:
        writer.writerow(
            {
                "library_id": ad.library_id,
                "page_name": ad.page_name,
                "page_id": ad.page_id,
                "status": ad.status,
                "score": ad.score,
                "badge": (ad.score_breakdown or {}).get("badge"),
                "days_running": ad.days_running,
                "start_date": ad.start_date,
                "end_date": ad.end_date,
                "media_type": ad.media_type,
                "variation_count": ad.variation_count,
                "platforms": "|".join(ad.platforms or []),
                "headline": ad.headline,
                "ad_copy": ad.ad_copy,
                "description": ad.description,
                "cta_text": ad.cta_text,
                "landing_url": ad.landing_url,
                "library_url": library_url(ad.library_id),
                "first_seen_at": ad.first_seen_at,
                "last_seen_at": ad.last_seen_at,
            }
        )
    return "﻿" + buf.getvalue()  # BOM so Excel on Windows opens UTF-8 correctly


@router.get("/{scan_id}/export.csv")
def export_scan_csv(scan_id: int) -> StreamingResponse:
    scan, comp = _get(scan_id)
    with session_scope() as session:
        ads = session.exec(
            select(Ad)
            .join(AdSnapshot, AdSnapshot.ad_id == Ad.id)
            .where(AdSnapshot.scan_id == scan_id)
            .order_by(Ad.score.desc())
        ).all()
    name = f"{slugify(comp.name if comp else 'scan')}-scan{scan_id}.csv"
    return StreamingResponse(
        iter([ads_to_csv(list(ads))]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
