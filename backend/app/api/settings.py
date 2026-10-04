from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlmodel import select

from app.analysis.scoring import compute_score
from app.core.config import ai_model, env, get_settings, save_override
from app.core.paths import data_dir
from app.db.models import Ad
from app.db.session import session_scope

router = APIRouter(prefix="/api/settings", tags=["settings"])

EDITABLE = {
    "scraping": {
        "driver",
        "headless",
        "delay_range",
        "long_pause_chance",
        "no_new_ads_attempts",
        "max_ads",
        "min_seconds_between_scans",
        "screenshots",
        "download_media",
        "download_videos",
        "max_media_mb",
        "max_media_per_ad",
        "page_load_timeout",
    },
    "scoring": {"weights", "thresholds", "longevity_full_days", "variations_log2_cap", "platforms_total"},
    "reports": {"agency_name", "primary_color", "accent_color", "logo_path"},
    "ai": {"model", "batch_size"},
}


def integrations() -> dict[str, Any]:
    return {
        "ai": {"configured": bool(env("ANTHROPIC_API_KEY")), "model": ai_model()},
        "telegram": {"configured": bool(env("TELEGRAM_BOT_TOKEN") and env("TELEGRAM_CHAT_ID"))},
        "email": {"configured": bool(env("SMTP_HOST") and env("SMTP_TO"))},
    }


def undetected_available() -> bool:
    try:
        import undetected_chromedriver  # type: ignore[import-not-found]  # noqa: F401

        return True
    except ImportError:
        return False


@router.get("")
def read_settings() -> dict:
    s = get_settings()
    return {
        "settings": {k: s.get(k, {}) for k in EDITABLE},
        "integrations": integrations(),
        "data_dir": str(data_dir()),
        "undetected_available": undetected_available(),
    }


def _rescore_all() -> int:
    with session_scope() as session:
        ads = session.exec(select(Ad)).all()
        for ad in ads:
            ad.score, ad.score_breakdown = compute_score(
                ad.days_running, ad.variation_count, ad.platforms, ad.status == "active"
            )
            session.add(ad)
        session.commit()
        return len(ads)


@router.put("")
async def update_settings(patch: dict[str, dict[str, Any]]) -> dict:
    clean: dict[str, dict[str, Any]] = {}
    for section, values in patch.items():
        allowed = EDITABLE.get(section)
        if allowed is None or not isinstance(values, dict):
            raise HTTPException(422, f"Unknown settings section: {section}")
        bad = set(values) - allowed
        if bad:
            raise HTTPException(422, f"Not editable: {', '.join(sorted(bad))}")
        clean[section] = values
    if "scoring" in clean and "weights" in clean["scoring"]:
        total = sum(float(v) for v in clean["scoring"]["weights"].values())
        if abs(total - 1.0) > 0.01:
            raise HTTPException(422, f"Scoring weights must add up to 1.0 (got {total:.2f})")
    save_override(clean)
    rescored = await run_in_threadpool(_rescore_all) if "scoring" in clean else 0
    return {**read_settings(), "rescored": rescored}


class NotifyTest(BaseModel):
    channel: Literal["telegram", "email"]


@router.post("/notify/test")
async def notify_test(body: NotifyTest) -> dict:
    from app.notify import send_test

    try:
        await run_in_threadpool(send_test, body.channel)
    except Exception as exc:  # noqa: BLE001 — show the provider's message to the user
        raise HTTPException(400, f"{body.channel.title()} test failed: {exc}") from exc
    return {"ok": True, "channel": body.channel}
