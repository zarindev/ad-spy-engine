"""Parser tests against real Ad Library HTML/JSON captured by scripts/capture_fixtures.py."""

from __future__ import annotations

import json
from datetime import date

import pytest

from app.scraper.parser import (
    AdRecord,
    clean_text,
    compress,
    compute_days_running,
    decompress,
    extract_connection_meta,
    extract_nodes_from_html,
    extract_nodes_from_payload,
    find_card_roots,
    matches_page,
    merge_records,
    parse_count,
    parse_human_date,
    parse_json_payload,
    parse_total_results,
    record_from_card_html,
    record_from_node,
    unwrap_redirect,
)

from .conftest import FIXTURE_TODAY, FIXTURES, read_fixture

CARD_FORMATS = sorted(p.stem.split("_card_")[1] for p in FIXTURES.glob("gymshark_card_*.html"))


# ----------------------------------------------------------------- JSON extraction
def test_server_rendered_page_contains_ads(page_html):
    nodes = extract_nodes_from_html(page_html)
    assert len(nodes) >= 10
    assert all(n["ad_archive_id"].isdigit() for n in nodes)
    assert {n["page_id"] for n in nodes} == {"129669023798560"}


def test_connection_meta_reads_total_count(page_html):
    meta = extract_connection_meta(page_html)
    assert isinstance(meta["count"], int) and meta["count"] > 100
    assert meta["captcha_required"] is False


def test_xhr_pagination_payloads_parse(xhr_payloads):
    assert xhr_payloads, "fixture should contain pagination responses"
    ids = [n["ad_archive_id"] for p in xhr_payloads for n in extract_nodes_from_payload(p)]
    assert len(ids) >= 10
    assert len(set(ids)) == len(ids)


def test_payload_with_for_loop_prefix_and_ndjson():
    body = 'for (;;);{"a": 1}\n{"b": 2}'
    assert parse_json_payload(body) == [{"a": 1}, {"b": 2}]
    assert parse_json_payload('{"x": [1]}') == [{"x": [1]}]


def test_every_fixture_node_maps_to_a_complete_record(page_html, xhr_payloads):
    nodes = extract_nodes_from_html(page_html) + [
        n for p in xhr_payloads for n in extract_nodes_from_payload(p)
    ]
    for node in nodes:
        rec = record_from_node(node, FIXTURE_TODAY)
        assert rec.library_id == node["ad_archive_id"]
        assert rec.page_name == "Gymshark"
        assert rec.status == "active"
        assert rec.start_date and rec.start_date <= FIXTURE_TODAY
        assert rec.days_running >= 1
        assert rec.platforms and all(p.isupper() for p in rec.platforms)
        assert rec.media_type in {"image", "video", "carousel", "dynamic", "catalog", "text"}
        assert rec.variation_count >= 1
        assert rec.thumbnail_url and rec.thumbnail_url.startswith("https://")
        assert rec.landing_url is None or "l.facebook.com" not in rec.landing_url


def test_video_node_exposes_video_and_poster():
    node = json.loads((FIXTURES / "gymshark_card_video.expected.json").read_text())
    rec = record_from_node(node, FIXTURE_TODAY)
    assert rec.media_type == "video"
    assert any("video" in u for u in rec.media_urls)
    assert rec.thumbnail_url


def test_dco_variations_count_versions():
    node = json.loads((FIXTURES / "gymshark_card_dco.expected.json").read_text())
    rec = record_from_node(node, FIXTURE_TODAY)
    expected = max(node.get("collation_count") or 1, len(node["snapshot"]["cards"]))
    assert rec.variation_count == expected >= 2


def test_dpa_template_text_falls_back_to_card_copy():
    node = json.loads((FIXTURES / "gymshark_card_dpa.expected.json").read_text())
    rec = record_from_node(node, FIXTURE_TODAY)
    assert rec.media_type in {"catalog", "video"}
    assert rec.ad_copy and "{{" not in rec.ad_copy


# ----------------------------------------------------------------- DOM fallback
@pytest.mark.parametrize("fmt", CARD_FORMATS)
def test_dom_card_parse_matches_json(fmt, selectors):
    html = read_fixture(f"gymshark_card_{fmt}.html")
    node = json.loads((FIXTURES / f"gymshark_card_{fmt}.expected.json").read_text())
    dom = record_from_card_html(html, selectors, FIXTURE_TODAY)
    js = record_from_node(node, FIXTURE_TODAY)
    assert dom is not None
    assert dom.library_id == js.library_id
    assert dom.page_name == "Gymshark"
    assert dom.status == "active"
    assert dom.start_date == js.start_date
    assert dom.days_running == js.days_running
    assert dom.ad_copy
    assert dom.raw_html == html


def test_find_card_roots_on_full_page(page_html, selectors):
    roots = find_card_roots(page_html, selectors["anchors"]["library_id"][:1])
    json_ids = {n["ad_archive_id"] for n in extract_nodes_from_html(page_html)}
    dom_ids = {record_from_card_html(str(r), selectors).library_id for r in roots}
    assert len(roots) >= 10
    assert dom_ids & json_ids  # server-rendered cards and JSON describe the same ads


def test_card_without_library_id_returns_none(selectors):
    assert record_from_card_html("<div><p>Hello</p></div>", selectors) is None


def test_merge_prefers_json_and_keeps_dom_html():
    js = AdRecord(library_id="1", ad_copy="json copy", platforms=["FACEBOOK"])
    dom = AdRecord(library_id="1", ad_copy="dom copy", cta_text="Shop now", raw_html="<div/>", source="dom")
    merged = merge_records(js, dom)
    assert merged.ad_copy == "json copy"
    assert merged.cta_text == "Shop now"
    assert merged.raw_html == "<div/>"
    assert merged.source == "json+dom"
    assert merge_records(None, dom) is dom


# ----------------------------------------------------------------- no results / counts
def test_no_results_page(selectors):
    html = read_fixture("no_results_page.html.gz")
    assert extract_nodes_from_html(html) == []
    assert extract_connection_meta(html)["count"] == 0
    assert "No ads match your search criteria" in selectors["anchors"]["no_results"]
    assert "No ads match your search criteria" in html


@pytest.mark.parametrize(
    "text,expected",
    [
        ("~120 results", 120),
        ("~1.2K results", 1200),
        ("1,234 results", 1234),
        ("~3 M results", 3_000_000),
        ("~45 resultados", 45),
    ],
)
def test_total_results(text, expected, selectors):
    assert parse_total_results(text, selectors["anchors"]["total_results"]) == expected


def test_parse_count_edge_cases():
    assert parse_count("~0") == 0
    assert parse_count("abc") is None


# ----------------------------------------------------------------- dates & helpers
@pytest.mark.parametrize(
    "text,expected",
    [
        ("20 Oct 2025", date(2025, 10, 20)),
        ("Oct 20, 2025", date(2025, 10, 20)),
        ("2 Jul 2026", date(2026, 7, 2)),
        ("20 oct. 2025", date(2025, 10, 20)),
        ("20 de oct de 2025", date(2025, 10, 20)),
        ("20. Okt. 2025", date(2025, 10, 20)),
        ("3 déc. 2025", date(2025, 12, 3)),
        ("12 März 2026", date(2026, 3, 12)),
        ("nonsense", None),
    ],
)
def test_parse_human_date(text, expected):
    assert parse_human_date(text) == expected


def test_days_running():
    today = date(2026, 10, 4)
    assert compute_days_running(date(2026, 10, 4), None, True, today) == 1
    assert compute_days_running(date(2026, 7, 2), None, True, today) == 95
    assert compute_days_running(date(2026, 1, 1), date(2026, 1, 10), False, today) == 10
    assert compute_days_running(None, None, True, today) == 0


def test_unwrap_redirect():
    wrapped = "https://l.facebook.com/l.php?u=http%3A%2F%2Fexample.com%2Fshop%3Fa%3D1&h=AT0"
    assert unwrap_redirect(wrapped) == "http://example.com/shop?a=1"
    assert unwrap_redirect("https://brand.com/x") == "https://brand.com/x"
    assert unwrap_redirect(None) is None


def test_clean_text_and_compression():
    assert clean_text(" ") is None
    assert clean_text({"text": " hi "}) == "hi"
    assert clean_text("​") is None
    assert decompress(compress("héllo")) == "héllo"


def test_matches_page():
    rec = AdRecord(library_id="1", page_name="Gymshark Women")
    assert matches_page(rec, "gymshark")
    assert matches_page(rec, "Gym Shark")
    assert not matches_page(rec, "nike")
