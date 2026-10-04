"""Change detection on synthetic scan histories."""

from __future__ import annotations

import itertools

from sqlmodel import select

from app.analysis.changes import detect_changes, has_changes
from app.db.models import Ad, AdSnapshot, ChangeEvent, Competitor, Scan
from app.db.session import session_scope

_ids = itertools.count(1)


def make_scan(session, comp_id: int, ads: dict[str, int], max_ads: int = 200, country: str = "US") -> int:
    """ads: {library_id: variation_count}. Creates ads/snapshots like a real scan would."""
    scan = Scan(
        competitor_id=comp_id,
        query="x",
        status="completed",
        ads_found=len(ads),
        max_ads=max_ads,
        country=country,
    )
    session.add(scan)
    session.flush()
    for lib, variations in ads.items():
        ad = session.exec(select(Ad).where(Ad.library_id == lib)).first()
        if ad is None:
            ad = Ad(
                library_id=lib,
                competitor_id=comp_id,
                status="active",
                days_running=10,
                platforms=["FACEBOOK"],
            )
        ad.variation_count = variations
        session.add(ad)
        session.flush()
        session.add(AdSnapshot(ad_id=ad.id, scan_id=scan.id, variation_count=variations, status="active"))
    session.flush()
    return scan.id  # type: ignore[return-value]


def new_competitor(session) -> int:
    n = next(_ids)
    comp = Competitor(name=f"Changes {n}", slug=f"changes-{n}")
    session.add(comp)
    session.flush()
    return comp.id  # type: ignore[return-value]


def p(n: int) -> str:
    return f"55{n:06d}"


def test_first_scan_is_baseline(migrated_db):
    with session_scope() as s:
        comp = new_competitor(s)
        sid = make_scan(s, comp, {p(1): 1, p(2): 1})
        summary = detect_changes(s, sid)
        s.commit()
        assert summary == {"baseline": True, "ads": 2}
        assert not has_changes(summary)


def test_new_stopped_scaled(migrated_db):
    with session_scope() as s:
        comp = new_competitor(s)
        first = make_scan(s, comp, {p(11): 1, p(12): 2, p(13): 1})
        detect_changes(s, first)
        second = make_scan(s, comp, {p(11): 1, p(12): 5, p(14): 1})  # 13 stopped, 14 new, 12 scaled
        summary = detect_changes(s, second)
        s.commit()
        assert summary["compared_to"] == first
        assert (summary["new"], summary["stopped"], summary["scaled"], summary["still_running"]) == (
            1,
            1,
            1,
            2,
        )
        kinds = {
            (e.kind, s.get(Ad, e.ad_id).library_id)
            for e in s.exec(select(ChangeEvent).where(ChangeEvent.scan_id == second)).all()
        }
        assert kinds == {("new", p(14)), ("stopped", p(13)), ("scaled", p(12))}
        stopped = s.exec(select(Ad).where(Ad.library_id == p(13))).first()
        assert stopped.status == "inactive" and stopped.score_breakdown["inputs"]["is_active"] is False


def test_capped_scan_does_not_infer_stopped(migrated_db):
    with session_scope() as s:
        comp = new_competitor(s)
        first = make_scan(s, comp, {p(21): 1, p(22): 1, p(23): 1})
        detect_changes(s, first)
        second = make_scan(s, comp, {p(21): 1, p(22): 1}, max_ads=2)  # hit the limit
        summary = detect_changes(s, second)
        assert summary["stopped"] == 0
        assert summary["stopped_check"].startswith("skipped")


def test_different_country_not_comparable(migrated_db):
    with session_scope() as s:
        comp = new_competitor(s)
        first = make_scan(s, comp, {p(31): 1, p(32): 1})
        detect_changes(s, first)
        second = make_scan(s, comp, {p(31): 1}, country="GB")
        summary = detect_changes(s, second)
        assert summary["stopped"] == 0 and "differ" in summary["stopped_check"]


def test_capped_previous_scan_separates_discovered_from_new(migrated_db):
    from datetime import date, timedelta

    with session_scope() as s:
        comp = new_competitor(s)
        first = make_scan(s, comp, {p(41): 1, p(42): 1}, max_ads=2)  # previous scan hit its limit
        detect_changes(s, first)
        second = make_scan(s, comp, {p(41): 1, p(42): 1, p(43): 1, p(44): 1})
        old = s.exec(select(Ad).where(Ad.library_id == p(43))).first()
        old.start_date = date.today() - timedelta(days=60)  # running long before → just beyond the old limit
        fresh = s.exec(select(Ad).where(Ad.library_id == p(44))).first()
        fresh.start_date = date.today()
        s.add(old)
        s.add(fresh)
        s.flush()
        summary = detect_changes(s, second)
        assert (summary["new"], summary["discovered"]) == (1, 1)
