"""Change detection between consecutive scans of the same competitor.

    new            first seen in this scan and launched since the previous scan
                   ("discovered" = first seen but older, when the previous scan hit its limit)
    stopped        present (and active) in the previous scan, missing now
    scaled         variation count went up since the previous scan
    still_running  present in both

"Stopped" is only inferred when the two scans are comparable (same country, search mode and
media filter) and the current scan was not cut off by its max_ads limit. Otherwise a missing ad
might just be beyond the limit, so no stopped events are recorded and the reason is kept in the
summary.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from app.analysis.scoring import compute_score
from app.db.models import Ad, AdSnapshot, ChangeEvent, Scan, ScanStatus

log = logging.getLogger(__name__)


def previous_scan(session: Session, scan: Scan) -> Scan | None:
    candidates = session.exec(
        select(Scan)
        .where(
            Scan.competitor_id == scan.competitor_id,
            Scan.id < scan.id,  # type: ignore[operator]
            Scan.status == ScanStatus.COMPLETED,
            Scan.ads_found > 0,
        )
        .order_by(Scan.id.desc())  # type: ignore[union-attr]
    ).all()
    for cand in candidates:  # prefer an identical setup
        if (cand.country, cand.search_type, cand.media_type) == (
            scan.country,
            scan.search_type,
            scan.media_type,
        ):
            return cand
    return candidates[0] if candidates else None


def comparable(a: Scan, b: Scan) -> bool:
    return (a.country, a.search_type, a.media_type, a.active_status) == (
        b.country,
        b.search_type,
        b.media_type,
        b.active_status,
    ) and sorted(a.platforms or []) == sorted(b.platforms or [])


def detect_changes(session: Session, scan_id: int) -> dict[str, Any]:
    """Record ChangeEvents for a finished scan and return its summary. Caller commits."""
    scan = session.get(Scan, scan_id)
    if scan is None:
        return {}
    current = {
        s.ad_id: s for s in session.exec(select(AdSnapshot).where(AdSnapshot.scan_id == scan_id)).all()
    }
    prev = previous_scan(session, scan)
    if prev is None:
        summary: dict[str, Any] = {"baseline": True, "ads": len(current)}
        scan.change_summary = summary
        session.add(scan)
        return summary

    previous = {
        s.ad_id: s for s in session.exec(select(AdSnapshot).where(AdSnapshot.scan_id == prev.id)).all()
    }
    # Ads whose earliest snapshot is this scan are brand new.
    first_seen = dict(
        session.exec(
            select(AdSnapshot.ad_id, func.min(AdSnapshot.scan_id))
            .where(AdSnapshot.ad_id.in_(list(current)))  # type: ignore[attr-defined]
            .group_by(AdSnapshot.ad_id)
        ).all()
    )
    first_time = [ad_id for ad_id in current if first_seen.get(ad_id) == scan_id]
    # If the previous scan stopped at its limit, an ad seen for the first time may simply have been
    # beyond that limit. Only ads that started running after the previous scan count as "new".
    prev_capped = prev.ads_found >= prev.max_ads
    prev_date = (prev.started_at or prev.created_at).date()
    new_ids: list[int] = []
    discovered = 0
    for ad_id in first_time:
        ad = session.get(Ad, ad_id)
        if prev_capped and ad is not None and ad.start_date is not None and ad.start_date < prev_date:
            discovered += 1
        else:
            new_ids.append(ad_id)
    both = [ad_id for ad_id in current if ad_id in previous]
    scaled = [ad_id for ad_id in both if current[ad_id].variation_count > previous[ad_id].variation_count]

    capped = scan.ads_found >= scan.max_ads
    stopped_check = "ok"
    if not comparable(scan, prev):
        stopped_check = "skipped: scan settings differ from the previous scan"
    elif capped:
        stopped_check = f"skipped: scan stopped at its {scan.max_ads}-ad limit"
    stopped = (
        [ad_id for ad_id, snap in previous.items() if ad_id not in current and snap.status == "active"]
        if stopped_check == "ok"
        else []
    )

    def event(ad_id: int, kind: str, details: dict[str, Any]) -> None:
        session.add(
            ChangeEvent(
                competitor_id=scan.competitor_id, scan_id=scan_id, ad_id=ad_id, kind=kind, details=details
            )
        )

    for ad_id in new_ids:
        event(ad_id, "new", {})
    for ad_id in scaled:
        event(
            ad_id, "scaled", {"from": previous[ad_id].variation_count, "to": current[ad_id].variation_count}
        )
    for ad_id in stopped:
        ad = session.get(Ad, ad_id)
        if ad is None:
            continue
        last_seen = ad.last_seen_at.date() if ad.last_seen_at else None
        ad.status = "inactive"
        ad.end_date = last_seen
        if ad.start_date and last_seen:
            ad.days_running = max((last_seen - ad.start_date).days, 0) + 1
        ad.score, ad.score_breakdown = compute_score(ad.days_running, ad.variation_count, ad.platforms, False)
        session.add(ad)
        event(ad_id, "stopped", {"days_running": ad.days_running, "last_seen": str(last_seen)})

    summary = {
        "baseline": False,
        "compared_to": prev.id,
        "new": len(new_ids),
        "discovered": discovered,
        "stopped": len(stopped),
        "scaled": len(scaled),
        "still_running": len(both),
        "stopped_check": stopped_check,
    }
    scan.change_summary = summary
    session.add(scan)
    log.info("Changes vs scan %s: %s", prev.id, summary)
    return summary


def has_changes(summary: dict[str, Any]) -> bool:
    return any(summary.get(k) for k in ("new", "stopped", "scaled"))
