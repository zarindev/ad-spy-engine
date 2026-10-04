"""Optional AI copy analysis with Claude (enabled only when ANTHROPIC_API_KEY is set).

Ads are sent in batches; Claude returns strict JSON (structured outputs) that is validated with
Pydantic and cached per Library ID, so an ad is never analyzed (or paid for) twice.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from collections.abc import Callable, Iterable
from typing import Any, Literal

from pydantic import BaseModel, ValidationError
from sqlmodel import Session, select

from app.core.config import ai_model, env, get_settings
from app.db.models import Ad, AdAnalysis, AiRun, utcnow

log = logging.getLogger(__name__)

HOOK_TYPES = ["question", "bold_claim", "problem_agitate", "social_proof", "curiosity", "offer", "story"]

# USD per million tokens (input, output) — Anthropic first-party list prices.
PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-fable-5-1": (10.0, 50.0),
}
DEFAULT_PRICE = (4.0, 20.0)
OUTPUT_TOKENS_PER_AD = 320  # JSON fields + reasoning at low effort (conservative estimate)
PROMPT_OVERHEAD_TOKENS = 700  # system prompt + schema per batch

SYSTEM_PROMPT = """You are a senior direct-response creative strategist analyzing competitors' Meta (Facebook/Instagram) ads for a marketing agency.

For every ad you receive, identify:
- hook_type: the opening technique, one of question | bold_claim | problem_agitate | social_proof | curiosity | offer | story
- hook_text: the exact opening line/phrase that functions as the hook (quote it from the copy)
- angle: the core persuasion angle in 2-5 words (e.g. "convenience for busy parents", "price vs. competitors")
- emotion: the primary emotion targeted, one or two words
- offer: the concrete offer (discount, free gift, trial, bundle) or null if none
- cta: the call to action as worded in the ad, or null
- target_audience_guess: who the ad is written for, one short phrase
- one_line_summary: what the ad says, in one plain sentence
- what_to_steal: one specific, actionable idea another brand could adapt from this ad (not generic advice)

Base everything on the ad text provided. Copy may contain unrendered catalog placeholders like {{product.name}}; treat them as dynamic product fields. Return one analysis per ad, echoing its library_id exactly."""


class Analysis(BaseModel):
    library_id: str
    hook_type: Literal[
        "question", "bold_claim", "problem_agitate", "social_proof", "curiosity", "offer", "story"
    ]
    hook_text: str | None
    angle: str | None
    emotion: str | None
    offer: str | None
    cta: str | None
    target_audience_guess: str | None
    one_line_summary: str | None
    what_to_steal: str | None


class BatchResult(BaseModel):
    analyses: list[Analysis]


def _nullable(kind: str = "string") -> dict[str, Any]:
    return {"type": [kind, "null"]}


OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "analyses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "library_id": {"type": "string"},
                    "hook_type": {"type": "string", "enum": HOOK_TYPES},
                    "hook_text": _nullable(),
                    "angle": _nullable(),
                    "emotion": _nullable(),
                    "offer": _nullable(),
                    "cta": _nullable(),
                    "target_audience_guess": _nullable(),
                    "one_line_summary": _nullable(),
                    "what_to_steal": _nullable(),
                },
                "required": [
                    "library_id",
                    "hook_type",
                    "hook_text",
                    "angle",
                    "emotion",
                    "offer",
                    "cta",
                    "target_audience_guess",
                    "one_line_summary",
                    "what_to_steal",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["analyses"],
    "additionalProperties": False,
}


class AIDisabled(RuntimeError):
    pass


def is_enabled() -> bool:
    return bool(env("ANTHROPIC_API_KEY"))


def ai_settings() -> dict[str, Any]:
    return get_settings().get("ai", {})


def price_for(model: str) -> tuple[float, float]:
    return PRICING.get(model, DEFAULT_PRICE)


def ad_payload(ad: Ad, max_chars: int) -> dict[str, Any]:
    copy = ad.ad_copy or ""
    return {
        "library_id": ad.library_id,
        "page": ad.page_name,
        "format": ad.media_type,
        "days_running": ad.days_running,
        "variations": ad.variation_count,
        "headline": ad.headline,
        "copy": copy[:max_chars] + (" …[truncated]" if len(copy) > max_chars else ""),
        "description": (ad.description or "")[:300] or None,
        "cta_button": ad.cta_text,
        "landing_url": ad.landing_url,
    }


def estimate_tokens(ads: Iterable[Ad], batch_size: int, max_chars: int) -> tuple[int, int]:
    ads = list(ads)
    if not ads:
        return 0, 0
    chars = sum(len(json.dumps(ad_payload(a, max_chars), ensure_ascii=False)) for a in ads)
    batches = -(-len(ads) // batch_size)
    input_tokens = int(chars / 3.2) + batches * PROMPT_OVERHEAD_TOKENS
    return input_tokens, len(ads) * OUTPUT_TOKENS_PER_AD


def split_cached(session: Session, ads: list[Ad]) -> tuple[list[Ad], int]:
    ids = [a.library_id for a in ads]
    cached = set(session.exec(select(AdAnalysis.library_id).where(AdAnalysis.library_id.in_(ids))).all())  # type: ignore[attr-defined]
    return [a for a in ads if a.library_id not in cached], len(cached)


def estimate(session: Session, ads: list[Ad]) -> dict[str, Any]:
    cfg = ai_settings()
    model = ai_model()
    todo, cached = split_cached(session, ads)
    inp, out = estimate_tokens(todo, int(cfg.get("batch_size", 10)), int(cfg.get("max_copy_chars", 1500)))
    pin, pout = price_for(model)
    return {
        "enabled": is_enabled(),
        "model": model,
        "ads": len(ads),
        "cached": cached,
        "to_analyze": len(todo),
        "input_tokens": inp,
        "output_tokens": out,
        "cost_usd": round(inp / 1e6 * pin + out / 1e6 * pout, 4),
        "pricing": {"input_per_mtok": pin, "output_per_mtok": pout},
        "note": "Estimate from character counts; actual usage is recorded per run.",
    }


# ----------------------------------------------------------------------------- Claude call
def make_client():  # noqa: ANN201
    import anthropic

    return anthropic.Anthropic(max_retries=3)


def analyze_batch(client: Any, model: str, ads: list[Ad], max_chars: int) -> tuple[list[Analysis], int, int]:
    """One structured-output request for a batch of ads. Returns (analyses, input_tokens, output_tokens)."""
    import anthropic

    payload = [ad_payload(a, max_chars) for a in ads]
    request: dict[str, Any] = {
        "model": model,
        "max_tokens": 16000,
        "system": SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": f"Analyze these {len(payload)} ads:\n\n{json.dumps(payload, ensure_ascii=False, indent=1)}",
            }
        ],
        "output_config": {"effort": "low", "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
    }
    try:
        # Server-side refusal fallback (Claude API): a declined request is retried on a fallback model.
        response = client.beta.messages.create(
            **request, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
        )
    except anthropic.BadRequestError as exc:
        if "fallback" not in str(exc).lower():
            raise
        response = client.messages.create(**request)  # e.g. proxies/platforms without the beta

    usage = getattr(response, "usage", None)
    in_tok = int(getattr(usage, "input_tokens", 0) or 0)
    out_tok = int(getattr(usage, "output_tokens", 0) or 0)
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to analyze this batch")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("Response hit max_tokens — lower ai.batch_size")
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        parsed = BatchResult.model_validate_json(text)
    except ValidationError as exc:
        raise RuntimeError(f"Invalid JSON from model: {exc.errors()[:1]}") from exc
    return parsed.analyses, in_tok, out_tok


def run_analysis(
    session: Session,
    run: AiRun,
    ads: list[Ad],
    client: Any | None = None,
    on_progress: Callable[[AiRun], None] | None = None,
) -> AiRun:
    if not is_enabled() and client is None:
        raise AIDisabled("Set ANTHROPIC_API_KEY in .env to enable AI analysis.")
    cfg = ai_settings()
    batch_size = max(1, int(cfg.get("batch_size", 10)))
    max_chars = int(cfg.get("max_copy_chars", 1500))
    client = client or make_client()
    todo, cached = split_cached(session, ads)
    run.status, run.total, run.cached = "running", len(todo), cached
    session.add(run)
    session.commit()
    pin, pout = price_for(run.model)
    by_lib = {a.library_id: a for a in todo}

    for start in range(0, len(todo), batch_size):
        batch = todo[start : start + batch_size]
        try:
            analyses, in_tok, out_tok = analyze_batch(client, run.model, batch, max_chars)
            run.input_tokens += in_tok
            run.output_tokens += out_tok
            returned = set()
            for item in analyses:
                ad = by_lib.get(item.library_id)
                if ad is None or item.library_id in returned:
                    continue
                returned.add(item.library_id)
                session.add(AdAnalysis(ad_id=ad.id, model=run.model, run_id=run.id, **item.model_dump()))
            run.done += len(returned)
            run.failed += len(batch) - len(returned)
        except Exception as exc:  # noqa: BLE001 — one failing batch never stops the run
            log.warning("AI batch failed: %s", exc)
            run.failed += len(batch)
            run.error = str(exc)[:500]
        run.cost_usd = round(run.input_tokens / 1e6 * pin + run.output_tokens / 1e6 * pout, 4)
        session.add(run)
        session.commit()
        if on_progress:
            on_progress(run)

    run.status = "completed" if run.done or not run.total else "failed"
    run.finished_at = utcnow()
    session.add(run)
    session.commit()
    return run


# ----------------------------------------------------------------------------- aggregates
def _norm(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().strip(".").lower() or None


def competitor_insights(session: Session, competitor_id: int) -> dict[str, Any]:
    rows = session.exec(
        select(AdAnalysis, Ad).join(Ad, Ad.id == AdAnalysis.ad_id).where(Ad.competitor_id == competitor_id)
    ).all()
    if not rows:
        return {"analyzed": 0}
    hooks = Counter(a.hook_type for a, _ in rows)
    angles = Counter(n for a, _ in rows if (n := _norm(a.angle)))
    emotions = Counter(n for a, _ in rows if (n := _norm(a.emotion)))
    offers = Counter(n for a, _ in rows if (n := _norm(a.offer)) and n not in {"none", "null", "n/a"})
    winners = sorted(rows, key=lambda r: -r[1].score)
    return {
        "analyzed": len(rows),
        "hook_distribution": [{"name": k, "count": v} for k, v in hooks.most_common()],
        "top_angles": [{"name": k, "count": v} for k, v in angles.most_common(8)],
        "emotions": [{"name": k, "count": v} for k, v in emotions.most_common(6)],
        "recurring_offers": [{"name": k, "count": v} for k, v in offers.most_common(6)],
        "steal_ideas": [
            {"ad_id": ad.id, "score": ad.score, "idea": a.what_to_steal, "hook": a.hook_text}
            for a, ad in winners[:8]
            if a.what_to_steal
        ],
    }


def analysis_out(a: AdAnalysis | None) -> dict[str, Any] | None:
    if a is None:
        return None
    return {
        "model": a.model,
        "hook_type": a.hook_type,
        "hook_text": a.hook_text,
        "angle": a.angle,
        "emotion": a.emotion,
        "offer": a.offer,
        "cta": a.cta,
        "target_audience_guess": a.target_audience_guess,
        "one_line_summary": a.one_line_summary,
        "what_to_steal": a.what_to_steal,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }
