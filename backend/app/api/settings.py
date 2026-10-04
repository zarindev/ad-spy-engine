from __future__ import annotations

import base64
import binascii
import hashlib
import re
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlmodel import select

from app.analysis.scoring import compute_score
from app.api.serializers import file_url
from app.core.config import ai_model, env, get_settings, save_override
from app.core.paths import data_dir, media_dir
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
    "reports": {"agency_name", "primary_color", "accent_color"},  # logo: POST /api/settings/logo
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
        "logo_url": file_url(s.get("reports", {}).get("logo_path")),
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
    for key in ("primary_color", "accent_color"):
        value = clean.get("reports", {}).get(key)
        if value is not None and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(value)):
            raise HTTPException(422, f"{key} must be a hex color like #6D28D9")
    if "agency_name" in clean.get("reports", {}):
        clean["reports"]["agency_name"] = str(clean["reports"]["agency_name"]).strip()[:80]
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


LOGO_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/svg+xml": ".svg"}
MAX_LOGO_BYTES = 2 * 1024 * 1024


class LogoUpload(BaseModel):
    data_url: str = Field(max_length=3_000_000)


@router.post("/logo")
def upload_logo(body: LogoUpload) -> dict:
    """Store the agency logo (sent as a data: URL) under data/media/_branding."""
    match = re.fullmatch(r"data:([\w/+.-]+);base64,(.+)", body.data_url, flags=re.S)
    if not match or match.group(1) not in LOGO_TYPES:
        raise HTTPException(422, "Upload a PNG, JPG, WebP or SVG image")
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(422, "The image could not be read") from exc
    if len(raw) > MAX_LOGO_BYTES:
        raise HTTPException(413, "Logo must be 2 MB or smaller")
    folder = media_dir() / "_branding"
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("logo-*"):
        old.unlink(missing_ok=True)
    path = folder / f"logo-{hashlib.sha1(raw).hexdigest()[:10]}{LOGO_TYPES[match.group(1)]}"
    path.write_bytes(raw)
    save_override({"reports": {"logo_path": path.relative_to(data_dir()).as_posix()}})
    return read_settings()


@router.delete("/logo")
def delete_logo() -> dict:
    folder = media_dir() / "_branding"
    for old in folder.glob("logo-*") if folder.exists() else []:
        old.unlink(missing_ok=True)
    save_override({"reports": {"logo_path": None}})
    return read_settings()


class ClearData(BaseModel):
    confirm: str


@router.post("/clear-data")
def clear_data(body: ClearData) -> dict:
    """Danger zone: delete every scan, ad, competitor, report and downloaded file. Settings stay."""
    import shutil

    from sqlmodel import delete

    from app.core.demo import require_live
    from app.core.paths import reports_dir
    from app.db.models import (
        AdAnalysis,
        AdSnapshot,
        AiRun,
        Board,
        BoardItem,
        ChangeEvent,
        Client,
        Competitor,
        LandingPage,
        Report,
        Scan,
        ScanStatus,
        WatchlistItem,
    )
    from app.jobs.scheduler import scheduler

    require_live()
    if body.confirm != "DELETE":
        raise HTTPException(422, "Type DELETE to confirm")
    with session_scope() as session:
        busy = session.exec(
            select(Scan).where(Scan.status.in_([ScanStatus.QUEUED, ScanStatus.RUNNING]))  # type: ignore[attr-defined]
        ).first()
        if busy is not None:
            raise HTTPException(409, "A scan is running. Cancel it first.")
        counts = {
            "ads": len(session.exec(select(Ad.id)).all()),
            "scans": len(session.exec(select(Scan.id)).all()),
        }
        for model in (
            BoardItem,
            Board,
            ChangeEvent,
            WatchlistItem,
            AdAnalysis,
            AiRun,
            AdSnapshot,
            Report,
            LandingPage,
            Ad,
            Scan,
            Competitor,
            Client,
        ):
            session.exec(delete(model))  # type: ignore[call-overload]
        session.commit()
    branding = media_dir() / "_branding"
    for folder in (media_dir(), reports_dir()):
        for child in folder.iterdir():
            if child == branding:
                continue  # the agency logo is a setting, not scan data
            shutil.rmtree(child) if child.is_dir() else child.unlink(missing_ok=True)
    scheduler.sync()
    return {"ok": True, "deleted": counts}
