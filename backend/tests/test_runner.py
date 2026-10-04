"""Persistence: upserts, snapshots, competitor merging — using real fixture records, no browser."""

from __future__ import annotations

from sqlmodel import select

from app.db.models import AdSnapshot, Competitor, Scan
from app.db.session import session_scope
from app.jobs.runner import adopt_page_name, create_scan, mark_interrupted_scans, upsert_ad
from app.scraper.ad_library import ScanParams
from app.scraper.parser import decompress, extract_nodes_from_html, record_from_node

from .conftest import FIXTURE_TODAY


def test_upsert_creates_ads_and_snapshots(migrated_db, page_html):
    scan = create_scan(ScanParams(query="Gymshark Test"))
    records = [record_from_node(n, FIXTURE_TODAY) for n in extract_nodes_from_html(page_html)[:5]]
    with session_scope() as session:
        results = [upsert_ad(session, r, scan.competitor_id, scan.id) for r in records]
        session.commit()
    assert all(is_new for _, is_new in results)

    scan2 = create_scan(ScanParams(query="Gymshark Test"))
    records[0].variation_count += 3
    with session_scope() as session:
        ad, is_new = upsert_ad(session, records[0], scan2.competitor_id, scan2.id)
        session.commit()
        assert not is_new
        assert ad.variation_count == records[0].variation_count
        snaps = session.exec(select(AdSnapshot).where(AdSnapshot.ad_id == ad.id)).all()
        assert {s.scan_id for s in snaps} == {scan.id, scan2.id}
        assert ad.score_breakdown["score"] == ad.score
        assert decompress(ad.raw_json)


def test_blank_reparse_does_not_erase_data(migrated_db, page_html):
    scan = create_scan(ScanParams(query="Erase Test"))
    rec = record_from_node(extract_nodes_from_html(page_html)[6], FIXTURE_TODAY)
    with session_scope() as session:
        upsert_ad(session, rec, scan.competitor_id, scan.id)
        session.commit()
    rec.ad_copy = None
    with session_scope() as session:
        ad, _ = upsert_ad(session, rec, scan.competitor_id, scan.id)
        session.commit()
        assert ad.ad_copy


def test_page_id_placeholder_merges_into_existing(migrated_db):
    keyword_scan = create_scan(ScanParams(query="Merge Brand"))
    page_scan = create_scan(ScanParams(query="999000111", search_type="page_id"))
    with session_scope() as session:
        assert session.get(Competitor, page_scan.competitor_id).name == "Page 999000111"
    merged = adopt_page_name(page_scan.competitor_id, page_scan.id, "Merge Brand")
    assert merged.id == keyword_scan.competitor_id
    assert merged.page_id == "999000111"
    with session_scope() as session:
        assert session.get(Scan, page_scan.id).competitor_id == merged.id


def test_interrupted_scans_are_marked(migrated_db):
    scan = create_scan(ScanParams(query="Crash Test"))
    with session_scope() as session:
        s = session.get(Scan, scan.id)
        s.status = "running"
        session.add(s)
        session.commit()
    assert mark_interrupted_scans() >= 1
    with session_scope() as session:
        assert session.get(Scan, scan.id).status == "interrupted"
