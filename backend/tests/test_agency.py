"""Phase 5: client folders, swipe file boards, compare and branded reports."""

from __future__ import annotations

import base64
import itertools
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.analysis.insights import ads_for, brand_summary, highlights, is_own_ad, opportunities_from_data
from app.analysis.scoring import compute_score
from app.db.models import Ad, Competitor, utcnow
from app.db.session import session_scope
from app.reports.builder import ReportSpec, normalize_sections, render_report

_lib = itertools.count(1)
FORMATS = ["video", "video", "image", "image", "carousel", "dynamic"]


def seed_brand(session, name: str, n: int, own_page: str, others: int = 0, long_days: int = 120) -> int:
    """A brand with `n` own ads (mixed formats and ages) plus `others` third-party ads."""
    slug = name.lower().replace(" ", "-")
    comp = Competitor(name=name, slug=slug)
    session.add(comp)
    session.flush()
    today = utcnow().date()
    for i in range(n + others):
        own = i < n
        days = long_days if i % 4 == 0 else 3 + i
        variations = 6 if i % 5 == 0 else 1
        platforms = ["FACEBOOK", "INSTAGRAM", "MESSENGER", "AUDIENCE_NETWORK"][: 1 + i % 4]
        score, breakdown = compute_score(days, variations, platforms, True)
        session.add(
            Ad(
                library_id=f"77{next(_lib):08d}",
                competitor_id=comp.id,
                page_name=own_page if own else f"Reseller {i}",
                status="active",
                start_date=today - timedelta(days=days - 1),
                days_running=days,
                platforms=platforms,
                media_type=FORMATS[i % len(FORMATS)],
                headline=f"{name} headline {i}",
                ad_copy=f"Copy {i} for {name}",
                cta_text="Shop now" if i % 2 else "Learn more",
                variation_count=variations,
                score=score,
                score_breakdown=breakdown,
            )
        )
    session.flush()
    return comp.id  # type: ignore[return-value]


@pytest.fixture(scope="module")
def api():
    from app.main import app

    with TestClient(app) as c:
        with session_scope() as s:
            c.alpha = seed_brand(s, "Alpha Labs", 24, "Alpha Labs", others=6)  # type: ignore[attr-defined]
            c.beta = seed_brand(s, "Beta Goods", 12, "Beta Goods Official", long_days=40)  # type: ignore[attr-defined]
            s.commit()
        yield c


# ----------------------------------------------------------------------------- insights
def test_own_page_filter_drops_other_advertisers(api):
    with session_scope() as s:
        comp = s.get(Competitor, api.alpha)
        own, excluded = ads_for(s, comp)
        everything, none = ads_for(s, comp, own_only=False)
    assert (len(own), excluded) == (24, 6)
    assert (len(everything), none) == (30, 0)
    assert all(is_own_ad(a, comp) for a in own)


def test_own_page_filter_falls_back_when_nothing_matches(migrated_db):
    with session_scope() as s:
        cid = seed_brand(s, "Zeta", 0, "Zeta", others=5)
        ads, excluded = ads_for(s, s.get(Competitor, cid))
        s.rollback()
    assert (len(ads), excluded) == (5, 0)


def test_highlights_and_opportunities_cite_real_numbers(api):
    with session_scope() as s:
        brands = []
        for cid in (api.alpha, api.beta):
            comp = s.get(Competitor, cid)
            ads, excluded = ads_for(s, comp)
            brands.append(brand_summary(s, comp, ads, excluded=excluded))
    alpha = brands[0]
    assert alpha["stats"]["ads"] == 24 and alpha["stats"]["other_advertisers_excluded"] == 6
    assert sum(f["count"] for f in alpha["formats"]) == 24
    assert sum(b["count"] for b in alpha["longevity"]) == 24
    lines = highlights(brands)
    assert any("median" in line for line in lines)
    opps = opportunities_from_data(brands)
    assert opps and all({"title", "detail", "evidence"} <= set(o) for o in opps)
    longest = next(o for o in opps if o["title"] == "Study the longest-running ad")
    assert "120 days" in longest["detail"]


# ----------------------------------------------------------------------------- clients
def test_client_folders_crud_and_assignment(api):
    res = api.post("/api/clients", json={"name": "Northwind", "competitor_ids": [api.alpha]})
    assert res.status_code == 201
    client = res.json()
    assert client["competitor_ids"] == [api.alpha]
    assert api.post("/api/clients", json={"name": "northwind"}).status_code == 409

    assert api.put(f"/api/clients/assign/{api.beta}", json={"client_id": client["id"]}).json()["ok"]
    listed = next(c for c in api.get("/api/clients").json() if c["id"] == client["id"])
    assert sorted(listed["competitor_ids"]) == sorted([api.alpha, api.beta])
    comps = {c["id"]: c for c in api.get("/api/competitors").json()}
    assert comps[api.beta]["client_id"] == client["id"]

    renamed = api.patch(f"/api/clients/{client['id']}", json={"name": "Northwind Fitness"}).json()
    assert renamed["name"] == "Northwind Fitness"
    api.client_id = client["id"]


def test_delete_client_keeps_competitors(api):
    tmp = api.post("/api/clients", json={"name": "Temp Client"}).json()
    api.put(f"/api/clients/assign/{api.beta}", json={"client_id": tmp["id"]})
    assert api.delete(f"/api/clients/{tmp['id']}").json()["ok"]
    comps = {c["id"]: c for c in api.get("/api/competitors").json()}
    assert api.beta in comps and comps[api.beta]["client_id"] is None
    api.put(f"/api/clients/assign/{api.beta}", json={"client_id": api.client_id})


def test_rename_competitor(api):
    res = api.patch(f"/api/competitors/{api.beta}", json={"name": "Beta Goods Co"})
    assert res.json()["name"] == "Beta Goods Co"
    api.patch(f"/api/competitors/{api.beta}", json={"name": "Beta Goods"})


# ----------------------------------------------------------------------------- boards
def test_swipe_board_lifecycle(api):
    ads = api.get(f"/api/ads?competitor_id={api.alpha}&limit=3").json()["items"]
    ids = [a["id"] for a in ads]
    board = api.post("/api/boards", json={"name": "Hooks we love", "ad_ids": ids[:2]}).json()
    assert board["item_count"] == 2 and len(board["covers"]) <= 2

    added = api.post(
        f"/api/boards/{board['id']}/items", json={"ad_ids": ids, "tags": ["UGC", " ugc", "#Hook"]}
    ).json()
    assert added["added"] == 1 and added["board"]["item_count"] == 3  # duplicates ignored
    assert board["id"] in api.get(f"/api/boards/for-ad/{ids[0]}").json()

    detail = api.get(f"/api/boards/{board['id']}").json()
    item = next(i for i in detail["items"] if i["ad"]["id"] == ids[2])
    assert item["tags"] == ["ugc", "hook"]
    patched = api.patch(
        f"/api/boards/{board['id']}/items/{item['id']}",
        json={"note": "Great opener", "tags": ["Offer", "offer"]},
    ).json()
    assert patched["note"] == "Great opener" and patched["tags"] == ["offer"]
    assert [i["ad"]["id"] for i in api.get(f"/api/boards/{board['id']}?tag=offer").json()["items"]] == [
        ids[2]
    ]
    assert {"name": "offer", "count": 1} in api.get("/api/boards/tags").json()

    renamed = api.patch(
        f"/api/boards/{board['id']}", json={"name": "Hooks", "client_id": api.client_id}
    ).json()
    assert renamed["name"] == "Hooks" and renamed["client_name"] == "Northwind Fitness"
    assert api.delete(f"/api/boards/{board['id']}/ads/{ids[0]}").json()["ok"]
    assert api.delete(f"/api/boards/{board['id']}/items/{item['id']}").json()["ok"]
    assert api.get(f"/api/boards/{board['id']}").json()["item_count"] == 1
    assert api.delete(f"/api/boards/{board['id']}").json()["ok"]
    assert api.get(f"/api/boards/{board['id']}").status_code == 404


# ----------------------------------------------------------------------------- compare
def test_compare_endpoint(api):
    data = api.get(f"/api/compare?ids={api.alpha},{api.beta}").json()
    assert [b["name"] for b in data["brands"]] == ["Alpha Labs", "Beta Goods"]
    assert data["brands"][0]["stats"]["ads"] == 24
    assert len(data["brands"][0]["top_ads"]) == 4 and len(data["brands"][0]["cadence"]) == 12
    assert data["highlights"] and data["opportunities"]
    everything = api.get(f"/api/compare?ids={api.alpha}&own_only=false").json()
    assert everything["brands"][0]["stats"]["ads"] == 30
    assert api.get("/api/compare?ids=1,2,3,4").status_code == 422
    assert api.get("/api/compare?ids=abc").status_code == 422


# ----------------------------------------------------------------------------- reports
def test_sections_normalize_legacy_names():
    assert normalize_sections(["all_ads", "top_ads", "summary", "bogus"]) == [
        "summary",
        "winners",
        "appendix",
    ]


def test_branded_report_html(api):
    path, meta = render_report(
        ReportSpec(
            competitor_ids=[api.alpha, api.beta],
            client_name="Northwind Fitness",
            sections=normalize_sections(None),
        )
    )
    html = path.read_text(encoding="utf-8")
    assert "Prepared for <b>Northwind Fitness</b>" in html
    assert "Opportunities for Northwind Fitness" in html and "Derived from the data" in html
    assert "Side by side" in html and "counter(pages)" in html
    assert "6 ads from other advertisers" in html
    assert meta["opportunities_source"] == "data" and meta["ads"] == 36


def test_report_with_ai_opportunities_uses_model_output(api):
    from types import SimpleNamespace

    class FakeAI:
        def __init__(self):
            self.beta = SimpleNamespace(messages=self)
            self.requests = []

        def create(self, **req):
            self.requests.append(req)
            lib = req["messages"][0]["content"].split('"library_id": "')[1].split('"')[0]
            text = (
                '{"executive_summary": "Alpha Labs dominates with long-running video.", "opportunities": '
                f'[{{"title": "Test a 120-day style demo", "why": "Ran 120 days.", "how_to_apply": "Film a demo.", '
                f'"evidence_library_ids": ["{lib}", "nope"]}}]}}'
            )
            return SimpleNamespace(
                stop_reason="end_turn",
                content=[SimpleNamespace(type="text", text=text)],
                usage=SimpleNamespace(input_tokens=4000, output_tokens=600),
            )

    fake = FakeAI()
    path, meta = render_report(
        ReportSpec(competitor_ids=[api.alpha], client_name="Northwind", use_ai=True), ai_client=fake
    )
    html = path.read_text(encoding="utf-8")
    assert "AI summary" in html and "Alpha Labs dominates" in html
    assert "Test a 120-day style demo" in html and "AI-generated" in html
    assert meta["ai_usage"]["input_tokens"] == 4000 and meta["ai_usage"]["cost_usd"] > 0
    assert fake.requests[0]["output_config"]["format"]["type"] == "json_schema"


def test_report_ai_failure_falls_back_to_data(api):
    class Broken:
        @property
        def beta(self):
            raise RuntimeError("network down")

    path, meta = render_report(ReportSpec(competitor_ids=[api.alpha], use_ai=True), ai_client=Broken())
    assert "network down" in meta["ai_usage"]["error"] and meta["opportunities_source"] == "data"
    assert "Derived from the data" in path.read_text(encoding="utf-8")


def test_report_api_scopes(api):
    ok = api.post(
        "/api/reports", json={"kind": "client", "client_id": api.client_id, "pdf": False, "top_n": 5}
    ).json()
    assert ok["status"] == "ready" and ok["kind"] == "client"
    assert ok["title"] == "Northwind Fitness: competitor landscape"
    assert sorted(ok["competitor_ids"]) == sorted([api.alpha, api.beta])
    assert api.get(ok["html_url"]).status_code == 200

    cmp = api.post("/api/reports", json={"kind": "compare", "competitor_ids": [api.alpha], "pdf": False})
    assert cmp.status_code == 422
    empty = api.post("/api/clients", json={"name": "Empty Client"}).json()
    res = api.post("/api/reports", json={"kind": "client", "client_id": empty["id"], "pdf": False})
    assert res.status_code == 422 and "no competitors" in res.json()["detail"]
    assert api.post("/api/reports", json={"kind": "scan", "scan_id": 999999, "pdf": False}).status_code == 404


# ----------------------------------------------------------------------------- branding
PNG_1PX = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


def test_logo_upload_and_branding_validation(api):
    res = api.post("/api/settings/logo", json={"data_url": f"data:image/png;base64,{PNG_1PX}"})
    assert res.status_code == 200
    logo_url = res.json()["logo_url"]
    assert logo_url.startswith("/files/media/_branding/logo-") and api.get(logo_url).status_code == 200

    path, _ = render_report(ReportSpec(competitor_ids=[api.alpha], sections=["cover"]))
    assert "data:image/png;base64," + PNG_1PX[:20] in path.read_text(encoding="utf-8")

    assert api.post("/api/settings/logo", json={"data_url": "data:text/html;base64,PGI+"}).status_code == 422
    big = base64.b64encode(b"0" * (2 * 1024 * 1024 + 10)).decode()
    assert api.post("/api/settings/logo", json={"data_url": f"data:image/png;base64,{big}"}).status_code in (
        413,
        422,
    )
    assert api.put("/api/settings", json={"reports": {"primary_color": "red"}}).status_code == 422
    assert api.put("/api/settings", json={"reports": {"logo_path": "app.db"}}).status_code == 422
    assert api.delete("/api/settings/logo").json()["logo_url"] is None


def test_clear_data_requires_confirmation(api):
    assert api.post("/api/settings/clear-data", json={"confirm": "yes"}).status_code == 422


def test_demo_mode_blocks_live_actions(api, monkeypatch):
    monkeypatch.setenv("ADSPY_DEMO", "1")
    assert api.get("/api/health").json()["demo"] is True
    for path, body in [
        ("/api/scans", {"query": "Nike"}),
        ("/api/ai/runs", {"competitor_id": api.alpha}),
        ("/api/settings/clear-data", {"confirm": "DELETE"}),
    ]:
        res = api.post(path, json=body)
        assert res.status_code == 403 and "Demo mode" in res.json()["detail"]
