"""AI analysis with a fake Anthropic client (no network, no key)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.analysis import ai
from app.db.models import AdAnalysis, AiRun
from app.db.session import session_scope
from app.jobs.runner import create_scan, upsert_ad
from app.scraper.ad_library import ScanParams
from app.scraper.parser import extract_nodes_from_html, record_from_node

from .conftest import FIXTURE_TODAY


class FakeMessages:
    def __init__(self, drop_last: bool = False) -> None:
        self.calls: list[dict] = []
        self.drop_last = drop_last

    def create(self, **kwargs):
        self.calls.append(kwargs)
        ads = json.loads(kwargs["messages"][0]["content"].split("\n\n", 1)[1])
        if self.drop_last:
            ads = ads[:-1]
        body = {
            "analyses": [
                {
                    "library_id": a["library_id"],
                    "hook_type": "bold_claim",
                    "hook_text": (a["copy"] or "")[:30],
                    "angle": "Convenience",
                    "emotion": "relief",
                    "offer": None,
                    "cta": a["cta_button"],
                    "target_audience_guess": "busy adults",
                    "one_line_summary": "x",
                    "what_to_steal": "Lead with the number",
                }
                for a in ads
            ]
        }
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=json.dumps(body))],
            usage=SimpleNamespace(input_tokens=1000, output_tokens=500),
        )


class FakeClient:
    def __init__(self, **kw) -> None:
        self.messages = FakeMessages(**kw)
        self.beta = SimpleNamespace(messages=self.messages)


@pytest.fixture
def seeded(migrated_db, page_html):
    scan = create_scan(ScanParams(query="AI Brand"))
    with session_scope() as session:
        ads = []
        for i, node in enumerate(extract_nodes_from_html(page_html)[:7]):
            rec = record_from_node(node, FIXTURE_TODAY)
            rec.library_id = f"7{i}{rec.library_id}"
            ad, _ = upsert_ad(session, rec, scan.competitor_id, scan.id)
            ads.append(ad)
        session.commit()
        return scan.competitor_id, [a.id for a in ads]


def test_disabled_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert ai.is_enabled() is False


def test_run_batches_caches_and_aggregates(seeded, monkeypatch):
    competitor_id, ad_ids = seeded
    monkeypatch.setattr(ai, "ai_settings", lambda: {"batch_size": 3, "max_copy_chars": 1500})
    from app.jobs.ai_worker import resolve_scope

    with session_scope() as session:
        ads = resolve_scope(session, {"competitor_id": competitor_id})
        est = ai.estimate(session, ads)
        assert est["to_analyze"] == len(ads) and est["cost_usd"] > 0
        client = FakeClient()
        run = AiRun(model="claude-sonnet-5-5", scope={})
        session.add(run)
        session.commit()
        ai.run_analysis(session, run, ads, client=client)
        assert run.status == "completed"
        assert run.done == len(ads) and run.failed == 0
        assert len(client.messages.calls) == -(-len(ads) // 3)  # batched
        call = client.messages.calls[0]
        assert call["output_config"]["format"]["type"] == "json_schema"
        assert call["fallbacks"] == "default"
        assert run.cost_usd == pytest.approx((run.input_tokens * 2 + run.output_tokens * 10) / 1e6)

        # Second run: everything cached, no API calls.
        client2 = FakeClient()
        run2 = AiRun(model="claude-sonnet-5-5", scope={})
        session.add(run2)
        session.commit()
        ai.run_analysis(session, run2, ads, client=client2)
        assert client2.messages.calls == [] and run2.cached == len(ads)

        insights = ai.competitor_insights(session, competitor_id)
        assert insights["analyzed"] == len(ads)
        assert insights["hook_distribution"][0] == {"name": "bold_claim", "count": len(ads)}
        assert insights["top_angles"][0]["name"] == "convenience"


def test_missing_items_count_as_failed(migrated_db, page_html, monkeypatch):
    monkeypatch.setattr(ai, "ai_settings", lambda: {"batch_size": 10})
    scan = create_scan(ScanParams(query="AI Partial"))
    with session_scope() as session:
        ads = []
        for i, node in enumerate(extract_nodes_from_html(page_html)[:3]):
            rec = record_from_node(node, FIXTURE_TODAY)
            rec.library_id = f"6{i}{rec.library_id}"
            ads.append(upsert_ad(session, rec, scan.competitor_id, scan.id)[0])
        session.commit()
        run = AiRun(model="claude-sonnet-5-5", scope={})
        session.add(run)
        session.commit()
        ai.run_analysis(session, run, ads, client=FakeClient(drop_last=True))
        assert (run.done, run.failed) == (2, 1)
        assert session.get(AdAnalysis, 1) is not None
