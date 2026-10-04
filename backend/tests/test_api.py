"""API tests (no browser): seeded from real fixture records into the isolated test DB."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db.session import session_scope
from app.jobs.runner import create_scan, upsert_ad
from app.jobs.worker import worker
from app.scraper.ad_library import ScanParams
from app.scraper.parser import extract_nodes_from_html, record_from_node

from .conftest import FIXTURE_TODAY


@pytest.fixture(scope="module")
def client(page_html):
    from app.main import app

    with TestClient(app) as c:
        scan = create_scan(ScanParams(query="API Brand"))
        with session_scope() as session:
            for node in extract_nodes_from_html(page_html)[:12]:
                upsert_ad(session, record_from_node(node, FIXTURE_TODAY), scan.competitor_id, scan.id)
            session.commit()
        c.scan_id = scan.id  # type: ignore[attr-defined]
        yield c


def test_health(client):
    assert client.get("/api/health").json()["ok"] is True


def test_dashboard(client):
    data = client.get("/api/stats/dashboard").json()
    assert data["kpis"]["ads_tracked"] >= 12
    assert len(data["ads_per_day"]) == 14
    assert {b["name"] for b in data["badges"]} == {"winner", "promising", "testing"}


def test_ads_list_filter_sort(client):
    res = client.get(f"/api/ads?scan_id={client.scan_id}&sort=days&limit=5").json()
    assert res["total"] == 12
    days = [a["days_running"] for a in res["items"]]
    assert days == sorted(days, reverse=True)
    winners = client.get(f"/api/ads?scan_id={client.scan_id}&badge=winner").json()
    assert all(a["badge"] == "winner" for a in winners["items"])
    ig = client.get(f"/api/ads?scan_id={client.scan_id}&platform=INSTAGRAM").json()
    assert all("INSTAGRAM" in a["platforms"] for a in ig["items"])


def test_ad_detail_has_breakdown_and_history(client):
    ad_id = client.get(f"/api/ads?scan_id={client.scan_id}&limit=1").json()["items"][0]["id"]
    detail = client.get(f"/api/ads/{ad_id}").json()
    assert set(detail["score_breakdown"]["components"]) == {"longevity", "variations", "platforms", "recency"}
    assert detail["history"][0]["scan_id"] == client.scan_id
    assert client.get("/api/ads/999999").status_code == 404


def test_csv_export(client):
    res = client.get(f"/api/scans/{client.scan_id}/export.csv")
    assert res.status_code == 200
    import csv
    import io

    rows = list(csv.DictReader(io.StringIO(res.text.lstrip("\ufeff"))))
    assert len(rows) == 12
    assert rows[0]["library_id"].isdigit() and rows[0]["library_url"].startswith("https://")


def test_scan_list_and_log(client):
    scans = client.get("/api/scans").json()
    assert any(s["id"] == client.scan_id for s in scans["items"])
    assert client.get(f"/api/scans/{client.scan_id}/log").status_code == 200


def test_start_scan_validates_and_enqueues(client, monkeypatch):
    queued: list[int] = []
    monkeypatch.setattr(worker, "enqueue", queued.append)
    assert client.post("/api/scans", json={"query": "abc", "search_type": "page_id"}).status_code == 422
    assert client.post("/api/scans", json={"query": ""}).status_code == 422
    res = client.post("/api/scans", json={"query": "Brewlab", "max_ads": 20})
    assert res.status_code == 201
    assert queued == [res.json()["id"]]
    assert res.json()["status"] == "queued"


def test_cancel_finished_scan_conflicts(client):
    from app.db.models import Scan

    with session_scope() as session:
        s = session.get(Scan, client.scan_id)
        s.status = "completed"
        session.add(s)
        session.commit()
    assert client.post(f"/api/scans/{client.scan_id}/cancel").status_code == 409


def test_settings_validation(client):
    data = client.get("/api/settings").json()
    assert "scraping" in data["settings"]
    assert client.put("/api/settings", json={"scraping": {"secret": 1}}).status_code == 422
    bad = {"scoring": {"weights": {"longevity": 0.9, "variations": 0.9, "platforms": 0.1, "recency": 0.1}}}
    assert client.put("/api/settings", json=bad).status_code == 422


def test_report_html_without_pdf(client):
    res = client.post(
        "/api/reports", json={"scan_id": client.scan_id, "pdf": False, "sections": ["summary", "top_ads"]}
    )
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "ready" and body["html_url"].startswith("/files/reports/")
    assert client.get(body["html_url"]).status_code == 200


def test_files_mount_does_not_expose_database(client):
    assert client.get("/files/app.db").status_code in (404, 503)
    assert client.get("/files/media/../app.db").status_code in (404, 503)


def test_competitor_profile_and_grouped_list(client):
    comp_id = client.get(f"/api/scans/{client.scan_id}").json()["competitor_id"]
    assert client.post(f"/api/competitors/{comp_id}/regroup").json()["ads"] >= 12
    prof = client.get(f"/api/competitors/{comp_id}/profile").json()
    assert prof["competitor"]["ad_count"] >= 12
    assert len(prof["timeline"]) >= 26
    assert sum(b["count"] for b in prof["longevity"]) == prof["competitor"]["ad_count"]
    full = client.get(f"/api/ads?competitor_id={comp_id}&limit=500").json()
    grouped = client.get(f"/api/ads?competitor_id={comp_id}&grouped=true&limit=500").json()
    assert grouped["total"] <= full["total"]
    assert len({a["group_key"] for a in grouped["items"]}) == len(grouped["items"])


def test_ad_detail_phase3_fields(client):
    ad_id = client.get(f"/api/ads?scan_id={client.scan_id}&limit=1").json()["items"][0]["id"]
    detail = client.get(f"/api/ads/{ad_id}").json()
    assert {"group", "landing_page", "analysis", "landing_capturable"} <= set(detail)
    assert "label" in detail["group"]


def test_ai_endpoints_without_key(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert client.get("/api/ai/status").json()["enabled"] is False
    est = client.post("/api/ai/estimate", json={"scan_id": client.scan_id}).json()
    assert est["to_analyze"] >= 1 and est["cost_usd"] > 0
    assert client.post("/api/ai/runs", json={"scan_id": client.scan_id}).status_code == 400
