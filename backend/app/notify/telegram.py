"""Telegram alerts through the Bot API (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID)."""

from __future__ import annotations

import httpx

from app.core.config import env


def configured() -> bool:
    return bool(env("TELEGRAM_BOT_TOKEN") and env("TELEGRAM_CHAT_ID"))


def send(html: str, timeout: float = 15.0) -> None:
    """Send an HTML-formatted message. Raises RuntimeError with Telegram's reason on failure."""
    token, chat_id = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("Telegram is not configured (set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)")
    resp = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": html[:4000],
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=timeout,
    )
    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    if resp.status_code != 200 or not data.get("ok", False):
        raise RuntimeError(f"Telegram error {resp.status_code}: {data.get('description', resp.text[:200])}")
