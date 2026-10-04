"""Model → JSON shapes used by the frontend (kept explicit so the API is stable)."""

from __future__ import annotations

from typing import Any

from app.analysis.scoring import BADGES
from app.db.models import Ad, Competitor, Report, Scan


def file_url(relative: str | None) -> str | None:
    """Data-dir relative path → URL served by the /files mounts."""
    return f"/files/{relative}" if relative else None


def asset_url(value: str | None) -> str | None:
    """Local data-relative path or (legacy) remote URL."""
    if not value:
        return None
    return value if value.startswith("http") else file_url(value)


def library_url(library_id: str) -> str:
    return f"https://www.facebook.com/ads/library/?id={library_id}"


def ad_out(ad: Ad, detail: bool = False) -> dict[str, Any]:
    badge = (ad.score_breakdown or {}).get("badge", "testing")
    data: dict[str, Any] = {
        "id": ad.id,
        "library_id": ad.library_id,
        "competitor_id": ad.competitor_id,
        "page_name": ad.page_name,
        "page_id": ad.page_id,
        "page_profile_image": ad.page_profile_image,
        "status": ad.status,
        "start_date": ad.start_date.isoformat() if ad.start_date else None,
        "end_date": ad.end_date.isoformat() if ad.end_date else None,
        "days_running": ad.days_running,
        "platforms": ad.platforms or [],
        "headline": ad.headline,
        "ad_copy": ad.ad_copy if detail else (ad.ad_copy or "")[:400],
        "cta_text": ad.cta_text,
        "media_type": ad.media_type,
        "display_format": ad.display_format,
        "variation_count": ad.variation_count,
        "score": ad.score,
        "badge": badge,
        "badge_label": BADGES[badge]["label"],
        "screenshot_url": file_url(ad.screenshot_path),
        "thumbnail_url": file_url(ad.thumbnail_path) or ad.thumbnail_url,
        "landing_url": ad.landing_url,
        "library_url": library_url(ad.library_id),
        "first_seen_at": ad.first_seen_at.isoformat() if ad.first_seen_at else None,
        "last_seen_at": ad.last_seen_at.isoformat() if ad.last_seen_at else None,
    }
    if detail:
        data.update(
            {
                "description": ad.description,
                "cta_type": ad.cta_type,
                "media_urls": ad.media_urls or [],
                "media_files": [file_url(p) for p in ad.media_paths or []],
                "score_breakdown": ad.score_breakdown or {},
                "source": ad.source,
                "collation_id": ad.collation_id,
            }
        )
    return data


def scan_out(scan: Scan, competitor: Competitor | None = None) -> dict[str, Any]:
    duration = scan.duration_seconds
    return {
        "id": scan.id,
        "competitor_id": scan.competitor_id,
        "competitor_name": competitor.name if competitor else None,
        "competitor_logo": asset_url(competitor.logo_url) if competitor else None,
        "query": scan.query,
        "search_type": scan.search_type,
        "country": scan.country,
        "media_type": scan.media_type,
        "platforms": scan.platforms or [],
        "active_status": scan.active_status,
        "max_ads": scan.max_ads,
        "exact_page": scan.exact_page,
        "headless": scan.headless,
        "status": scan.status,
        "total_results": scan.total_results,
        "ads_found": scan.ads_found,
        "ads_processed": scan.ads_processed,
        "ads_failed": scan.ads_failed,
        "new_ads": scan.new_ads,
        "error": scan.error,
        "block_reason": scan.block_reason,
        "created_at": scan.created_at.isoformat() if scan.created_at else None,
        "started_at": scan.started_at.isoformat() if scan.started_at else None,
        "finished_at": scan.finished_at.isoformat() if scan.finished_at else None,
        "duration_seconds": duration,
        "ads_per_minute": round(scan.ads_found / duration * 60, 1) if duration else None,
    }


def competitor_out(c: Competitor, stats: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": c.id,
        "name": c.name,
        "page_id": c.page_id,
        "logo_url": asset_url(c.logo_url),
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "last_scan_at": c.last_scan_at.isoformat() if c.last_scan_at else None,
        **(stats or {}),
    }


def report_out(r: Report) -> dict[str, Any]:
    return {
        "id": r.id,
        "title": r.title,
        "kind": r.kind,
        "scan_id": r.scan_id,
        "competitor_ids": r.competitor_ids or [],
        "options": r.options or {},
        "html_url": file_url(r.html_path),
        "pdf_url": file_url(r.pdf_path),
        "status": r.status,
        "error": r.error,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }
