"""Scan orchestration: create a scan, run the scraper, persist ads/snapshots/media, score.

Used by both the CLI and the background worker. All DB writes happen on the scan thread;
media downloads run on a small pool and are attached to ads when they complete.
"""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Callable
from concurrent.futures import Future
from pathlib import Path
from typing import Any

import httpx
from sqlmodel import Session, select

from app.analysis.changes import detect_changes
from app.analysis.grouping import regroup_competitor
from app.analysis.scoring import compute_score
from app.core.config import get_settings
from app.core.logging import scan_log
from app.core.paths import slugify
from app.db.models import Ad, AdSnapshot, Competitor, Scan, ScanStatus, utcnow
from app.db.session import session_scope
from app.scraper.ad_library import AdLibraryScraper, ScanBlocked, ScanCancelled, ScanParams
from app.scraper.landing import capture_landing_pages, is_capturable, url_key
from app.scraper.media import (
    USER_AGENT,
    MediaDownloader,
    competitor_media_dir,
    download_file,
    relative_to_data,
)
from app.scraper.parser import AdRecord, compress

log = logging.getLogger(__name__)

EventFn = Callable[[str, dict[str, Any]], None]


# ------------------------------------------------------------------------------ setup
def get_or_create_competitor(session: Session, name: str, page_id: str | None = None) -> Competitor:
    if page_id:
        found = session.exec(select(Competitor).where(Competitor.page_id == page_id)).first()
        if found:
            return found
    slug = slugify(name)
    found = session.exec(select(Competitor).where(Competitor.slug == slug)).first()
    if found:
        if page_id and not found.page_id:
            found.page_id = page_id
        return found
    competitor = Competitor(name=name.strip(), slug=slug, page_id=page_id)
    session.add(competitor)
    session.flush()
    return competitor


def create_scan(params: ScanParams, competitor_name: str | None = None) -> Scan:
    with session_scope() as session:
        page_id = params.query.strip() if params.search_type == "page_id" else None
        name = competitor_name or (f"Page {page_id}" if page_id else params.query)
        competitor = get_or_create_competitor(session, name, page_id)
        scan = Scan(
            competitor_id=competitor.id,
            query=params.query.strip(),
            search_type=params.search_type,
            country=params.country.upper(),
            media_type=params.media_type,
            platforms=[p.lower() for p in params.platforms],
            active_status=params.active_status,
            max_ads=params.max_ads,
            exact_page=params.exact_page,
            headless=True if params.headless is None else params.headless,
        )
        session.add(scan)
        session.commit()
        session.refresh(scan)
        return scan


def params_from_scan(scan: Scan, driver_type: str | None = None) -> ScanParams:
    return ScanParams(
        query=scan.query,
        search_type=scan.search_type,
        country=scan.country,
        media_type=scan.media_type,
        platforms=list(scan.platforms or []),
        active_status=scan.active_status,
        max_ads=scan.max_ads,
        exact_page=scan.exact_page,
        headless=scan.headless,
        driver_type=driver_type,
    )


def seconds_until_allowed(session: Session, exclude_scan_id: int | None = None) -> float:
    """Rate limit: minimum seconds between the start of consecutive scans."""
    minimum = float(get_settings().get("scraping", {}).get("min_seconds_between_scans", 0))
    if minimum <= 0:
        return 0.0
    stmt = select(Scan).where(Scan.started_at.is_not(None)).order_by(Scan.started_at.desc())  # type: ignore[union-attr]
    for last in session.exec(stmt):
        if last.id == exclude_scan_id:
            continue
        elapsed = (utcnow() - last.started_at).total_seconds()
        return max(0.0, minimum - elapsed)
    return 0.0


# ------------------------------------------------------------------------------ persist
def upsert_ad(session: Session, record: AdRecord, competitor_id: int, scan_id: int) -> tuple[Ad, bool]:
    ad = session.exec(select(Ad).where(Ad.library_id == record.library_id)).first()
    is_new = ad is None
    if ad is None:
        ad = Ad(library_id=record.library_id, competitor_id=competitor_id)
    fields = record.to_dict()
    fields.pop("page_profile_uri", None)
    for key, value in fields.items():
        if key == "library_id":
            continue
        if value in (None, "", []) and getattr(ad, key, None) not in (None, "", []):
            continue  # never erase data we already have with a blank re-parse
        setattr(ad, key, value)
    if record.raw_html:
        ad.raw_html = compress(record.raw_html)
    if record.raw_json:
        ad.raw_json = compress(record.raw_json)
    score, breakdown = compute_score(ad.days_running, ad.variation_count, ad.platforms, ad.status == "active")
    ad.score, ad.score_breakdown = score, breakdown
    ad.last_seen_at = utcnow()
    ad.last_scan_id = scan_id
    session.add(ad)
    session.flush()
    snapshot = session.exec(
        select(AdSnapshot).where(AdSnapshot.ad_id == ad.id, AdSnapshot.scan_id == scan_id)
    ).first() or AdSnapshot(ad_id=ad.id, scan_id=scan_id)
    snapshot.status = ad.status
    snapshot.variation_count = ad.variation_count
    snapshot.days_running = ad.days_running
    snapshot.score = ad.score
    session.add(snapshot)
    return ad, is_new


def _update_scan(scan_id: int, **values: Any) -> Scan:
    with session_scope() as session:
        scan = session.get(Scan, scan_id)
        assert scan is not None
        for key, value in values.items():
            setattr(scan, key, value)
        session.add(scan)
        session.commit()
        session.refresh(scan)
        return scan


# ------------------------------------------------------------------------------ run
def run_scan(
    scan_id: int,
    on_event: EventFn | None = None,
    cancel: threading.Event | None = None,
    driver_type: str | None = None,
) -> Scan:
    emit = on_event or (lambda _k, _d: None)
    cancel = cancel or threading.Event()
    cfg = get_settings().get("scraping", {})

    with session_scope() as session:
        scan = session.get(Scan, scan_id)
        if scan is None:
            raise ValueError(f"Scan {scan_id} not found")
        competitor = session.get(Competitor, scan.competitor_id)
        assert competitor is not None
        wait = seconds_until_allowed(session, exclude_scan_id=scan_id)

    if wait > 0:
        log.info("Rate limit: waiting %.0fs before starting (min_seconds_between_scans)", wait)
        emit("status", {"status": "rate_limited", "wait_seconds": round(wait)})
        if cancel.wait(wait):
            return _update_scan(scan_id, status=ScanStatus.CANCELLED, finished_at=utcnow())

    with scan_log(scan_id) as log_path:
        scan = _update_scan(
            scan_id,
            status=ScanStatus.RUNNING,
            started_at=utcnow(),
            log_path=str(log_path),
            error=None,
            block_reason=None,
        )
        log.info("Scan %s started: %s (%s, %s)", scan_id, scan.query, scan.search_type, scan.country)
        emit("status", {"status": ScanStatus.RUNNING})

        pending: list[tuple[int, str, Future[Path | None]]] = []
        counters = {"new": 0}
        download_media = bool(cfg.get("download_media", True))
        download_videos = bool(cfg.get("download_videos", False))
        per_ad = int(cfg.get("max_media_per_ad", 4))
        # Resolved on the first ad: page-ID scans only learn the brand name from the results.
        ctx: dict[str, Any] = {"competitor": competitor, "folder": None, "downloader": None}

        def prepare(record: AdRecord) -> None:
            if ctx["folder"] is not None:
                return
            if (
                scan.search_type == "page_id"
                and record.page_id == scan.query
                and record.page_name
                and ctx["competitor"].name.startswith("Page ")
            ):
                ctx["competitor"] = adopt_page_name(ctx["competitor"].id, scan_id, record.page_name)
            slug = ctx["competitor"].slug
            ctx["folder"] = competitor_media_dir(slug)
            ctx["downloader"] = MediaDownloader(
                slug, int(cfg.get("media_workers", 4)), float(cfg.get("max_media_mb", 25))
            )

        def on_ad(record: AdRecord, png: bytes | None) -> None:
            prepare(record)
            with session_scope() as session:
                ad, is_new = upsert_ad(session, record, ctx["competitor"].id, scan_id)
                if png:
                    shot = ctx["folder"] / f"{record.library_id}.png"
                    shot.write_bytes(png)
                    ad.screenshot_path = relative_to_data(shot)
                session.add(ad)
                session.commit()
                ad_id, ad_payload = ad.id, ad_summary(ad)
            counters["new"] += int(is_new)
            counters["seen"] = counters.get("seen", 0) + 1
            if counters["seen"] % 10 == 0:  # partial counts survive a hard crash
                _update_scan(
                    scan_id,
                    ads_found=counters["seen"],
                    ads_processed=counters["seen"],
                    new_ads=counters["new"],
                )
            if download_media:
                downloader = ctx["downloader"]
                if record.thumbnail_url:
                    pending.append(
                        (
                            ad_id,
                            "thumb",
                            downloader.submit(record.thumbnail_url, f"{record.library_id}_thumb"),
                        )
                    )
                urls = [
                    u
                    for u in record.media_urls
                    if download_videos or not ("video" in u.split("?")[0] or ".mp4" in u)
                ]
                for i, url in enumerate(urls[:per_ad]):
                    pending.append((ad_id, "media", downloader.submit(url, f"{record.library_id}_{i}")))
            emit("ad", {"ad": ad_payload, "is_new": is_new})

        def on_scraper_event(kind: str, data: dict[str, Any]) -> None:
            if kind == "progress":
                emit("progress", data)
            else:
                emit(kind, data)

        scraper = AdLibraryScraper(params_from_scan(scan, driver_type), on_scraper_event, cancel)
        status, error, block_reason = ScanStatus.COMPLETED, None, None
        try:
            scraper.run(on_ad)
        except ScanCancelled:
            status = ScanStatus.CANCELLED
            log.info("Scan %s cancelled", scan_id)
        except ScanBlocked as exc:
            status, block_reason = ScanStatus.BLOCKED, exc.reason
            log.warning("Scan %s blocked: %s", scan_id, exc.reason)
            emit("blocked", {"reason": exc.reason, "suggestions": exc.suggestions})
        except Exception as exc:  # noqa: BLE001
            status, error = ScanStatus.FAILED, f"{type(exc).__name__}: {exc}"
            log.exception("Scan %s failed", scan_id)
        finally:
            if ctx["downloader"] is not None:
                ctx["downloader"].close()

        _attach_media(pending)
        stats = scraper.stats
        if stats.found:
            post_process(
                scan_id, ctx["competitor"].id, emit, cancel if status != ScanStatus.CANCELLED else None
            )
        _finalize_competitor(ctx["competitor"].id)
        scan = _update_scan(
            scan_id,
            status=status,
            error=error,
            block_reason=block_reason,
            total_results=stats.total_results,
            ads_found=stats.found,
            ads_processed=stats.processed,
            ads_failed=stats.failed,
            new_ads=counters["new"],
            finished_at=utcnow(),
        )
        if status == ScanStatus.COMPLETED and stats.found:
            try:
                with session_scope() as session:
                    detect_changes(session, scan_id)
                    session.commit()
                scan = _update_scan(scan_id)
            except Exception:  # noqa: BLE001
                log.exception("Change detection failed")
        log.info("Scan %s finished with status %s", scan_id, status)
        emit("status", {"status": status, "scan": scan_summary(scan)})
        return scan


def post_process(scan_id: int, competitor_id: int, emit: EventFn, cancel: threading.Event | None) -> None:
    """After collection: variation grouping, then landing page screenshots. Never fails a scan."""
    try:
        emit("status", {"status": "grouping"})
        with session_scope() as session:
            regroup_competitor(session, competitor_id)
            session.commit()
    except Exception:  # noqa: BLE001
        log.exception("Variation grouping failed")

    landing_cfg = get_settings().get("landing", {})
    if cancel is None or cancel.is_set() or not landing_cfg.get("enabled", True):
        return
    try:
        with session_scope() as session:
            competitor = session.get(Competitor, competitor_id)
            ads = session.exec(
                select(Ad)
                .join(AdSnapshot, AdSnapshot.ad_id == Ad.id)
                .where(AdSnapshot.scan_id == scan_id, Ad.landing_url.is_not(None))  # type: ignore[union-attr]
                .order_by(Ad.score.desc())  # type: ignore[attr-defined]
            ).all()
            urls: list[str] = []
            seen: set[str] = set()
            for ad in ads:
                key = url_key(ad.landing_url)
                if key and key not in seen and is_capturable(ad.landing_url):
                    seen.add(key)
                    urls.append(ad.landing_url)  # type: ignore[arg-type]
                if len(urls) >= int(landing_cfg.get("max_per_scan", 10)):
                    break
            if not urls or competitor is None:
                return
            emit("status", {"status": "capturing_landing_pages", "count": len(urls)})
            log.info("Capturing up to %d landing pages", len(urls))
            capture_landing_pages(
                session,
                urls,
                competitor.slug,
                cancel,
                on_progress=lambda i, n: emit("landing_progress", {"done": i, "total": n}),
            )
    except Exception:  # noqa: BLE001
        log.exception("Landing page capture failed")


def _attach_media(pending: list[tuple[int, str, Future[Path | None]]]) -> None:
    if not pending:
        return
    by_ad: dict[int, dict[str, Any]] = {}
    for ad_id, kind, future in pending:
        try:
            path = future.result(timeout=120)
        except Exception:  # noqa: BLE001
            path = None
        if path is None:
            continue
        entry = by_ad.setdefault(ad_id, {"thumb": None, "media": []})
        if kind == "thumb":
            entry["thumb"] = relative_to_data(path)
        else:
            entry["media"].append(relative_to_data(path))
    with session_scope() as session:
        for ad_id, entry in by_ad.items():
            ad = session.get(Ad, ad_id)
            if ad is None:
                continue
            if entry["thumb"]:
                ad.thumbnail_path = entry["thumb"]
            if entry["media"]:
                ad.media_paths = sorted(set((ad.media_paths or []) + entry["media"]))
            session.add(ad)
        session.commit()
    log.info("Attached downloaded media to %d ads", len(by_ad))


def adopt_page_name(competitor_id: int, scan_id: int, page_name: str) -> Competitor:
    """Rename a placeholder "Page <id>" competitor, merging into an existing one with that name."""
    with session_scope() as session:
        placeholder = session.get(Competitor, competitor_id)
        assert placeholder is not None
        existing = session.exec(
            select(Competitor).where(Competitor.slug == slugify(page_name), Competitor.id != competitor_id)
        ).first()
        if existing is None:
            placeholder.name, placeholder.slug = page_name, slugify(page_name)
            session.add(placeholder)
            session.commit()
            session.refresh(placeholder)
            return placeholder
        existing.page_id = existing.page_id or placeholder.page_id
        for model in (Scan, Ad):
            for row in session.exec(select(model).where(model.competitor_id == competitor_id)).all():
                row.competitor_id = existing.id
                session.add(row)
        session.flush()
        session.delete(placeholder)
        session.commit()
        session.refresh(existing)
        log.info("Merged placeholder competitor into existing %r", existing.name)
        return existing


def download_logo(slug: str, url: str) -> str | None:
    """Profile-image URLs expire, so keep a local copy (data-relative path)."""
    with httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        path = download_file(client, url, competitor_media_dir(slug) / "_logo", 2_000_000)
    return relative_to_data(path) if path else None


def _adopt_display_casing(session: Session, competitor: Competitor) -> None:
    """Keyword scans store the typed query ("huel"); prefer the page's own casing ("Huel")."""
    if competitor.name != competitor.name.lower():
        return
    target = re.sub(r"[^a-z0-9]", "", competitor.name.lower())
    names = session.exec(
        select(Ad.page_name).where(Ad.competitor_id == competitor.id, Ad.page_name.is_not(None))  # type: ignore[union-attr]
    ).all()
    for name in names:
        if name and re.sub(r"[^a-z0-9]", "", name.lower()) == target:
            competitor.name = name
            return


def _finalize_competitor(competitor_id: int) -> None:
    with session_scope() as session:
        competitor = session.get(Competitor, competitor_id)
        if competitor is None:
            return
        competitor.last_scan_at = utcnow()
        _adopt_display_casing(session, competitor)
        if not competitor.logo_url or competitor.logo_url.startswith("http"):
            stmt = select(Ad).where(
                Ad.competitor_id == competitor_id, Ad.page_profile_image.is_not(None)  # type: ignore[union-attr]
            )
            if competitor.page_id:
                stmt = stmt.where(Ad.page_id == competitor.page_id)
            ad = session.exec(stmt.order_by(Ad.last_seen_at.desc())).first()  # type: ignore[attr-defined]
            if ad and ad.page_profile_image:
                competitor.logo_url = download_logo(competitor.slug, ad.page_profile_image)
        session.add(competitor)
        session.commit()


# ------------------------------------------------------------------------------ views
def ad_summary(ad: Ad) -> dict[str, Any]:
    return {
        "id": ad.id,
        "library_id": ad.library_id,
        "page_name": ad.page_name,
        "status": ad.status,
        "start_date": ad.start_date.isoformat() if ad.start_date else None,
        "days_running": ad.days_running,
        "platforms": ad.platforms,
        "media_type": ad.media_type,
        "variation_count": ad.variation_count,
        "score": ad.score,
        "badge": (ad.score_breakdown or {}).get("badge"),
        "headline": ad.headline,
        "ad_copy": (ad.ad_copy or "")[:280],
        "screenshot_path": ad.screenshot_path,
        "thumbnail_url": ad.thumbnail_url,
    }


def scan_summary(scan: Scan) -> dict[str, Any]:
    return {
        "id": scan.id,
        "status": scan.status,
        "query": scan.query,
        "total_results": scan.total_results,
        "ads_found": scan.ads_found,
        "ads_failed": scan.ads_failed,
        "new_ads": scan.new_ads,
        "duration_seconds": scan.duration_seconds,
        "block_reason": scan.block_reason,
        "error": scan.error,
        "change_summary": scan.change_summary or {},
        "trigger": scan.trigger,
    }
