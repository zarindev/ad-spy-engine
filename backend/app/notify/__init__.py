"""Alert fan-out for watchlist scans: Telegram and/or email, whichever is configured."""

from __future__ import annotations

import html
import logging
from typing import Any

from sqlmodel import Session, select

from app.db.models import Ad, ChangeEvent, Competitor, Scan
from app.notify import email, telegram

log = logging.getLogger(__name__)

APP_URL = "http://localhost:8000"


def channels() -> dict[str, bool]:
    return {"telegram": telegram.configured(), "email": email.configured()}


def build_alert(session: Session, scan: Scan) -> tuple[str, str, str]:
    """Return (subject, plain text, telegram/email HTML) for a scan's changes or failure."""
    comp = session.get(Competitor, scan.competitor_id)
    name = comp.name if comp else scan.query
    s = scan.change_summary or {}
    if scan.status in ("blocked", "failed"):
        subject = f"⚠️ Ad Spy Engine: scan of {name} {scan.status}"
        reason = scan.block_reason or scan.error or "see the scan log"
        text = f"The scheduled scan of {name} {scan.status}: {reason}"
        return subject, text, f"<b>⚠️ {html.escape(name)}</b> scan {scan.status}\n{html.escape(reason)}"

    subject = (
        f"📣 {name}: {s.get('new', 0)} new · {s.get('stopped', 0)} stopped · {s.get('scaled', 0)} scaled"
    )
    lines = [
        f"<b>📣 {html.escape(name)}</b> — watchlist scan #{scan.id}",
        f"🆕 {s.get('new', 0)} new   ⏹ {s.get('stopped', 0)} stopped   📈 {s.get('scaled', 0)} scaled   "
        f"▶️ {s.get('still_running', 0)} still running",
    ]
    events = session.exec(
        select(ChangeEvent, Ad)
        .join(Ad, Ad.id == ChangeEvent.ad_id)
        .where(ChangeEvent.scan_id == scan.id, ChangeEvent.kind.in_(["new", "scaled"]))  # type: ignore[attr-defined]
        .order_by(Ad.score.desc())  # type: ignore[attr-defined]
        .limit(5)
    ).all()
    if events:
        lines.append("\n<b>Worth a look:</b>")
        for ev, ad in events:
            label = "NEW" if ev.kind == "new" else f"SCALED {ev.details.get('from')}→{ev.details.get('to')}"
            copy = html.escape((ad.headline or ad.ad_copy or "").replace("\n", " ")[:90])
            lines.append(f"• [{label}] score {ad.score} — {copy}")
    lines.append(f'\n<a href="{APP_URL}/scans/{scan.id}">Open in Ad Spy Engine</a>')
    body = "\n".join(lines)
    text = body.replace("<b>", "").replace("</b>", "")
    text = text.replace(
        f'<a href="{APP_URL}/scans/{scan.id}">Open in Ad Spy Engine</a>', f"{APP_URL}/scans/{scan.id}"
    )
    return subject, text, body


def send_alert(session: Session, scan: Scan) -> dict[str, str]:
    """Send to every configured channel; one failing channel never blocks the other."""
    subject, text, body = build_alert(session, scan)
    results: dict[str, str] = {}
    if telegram.configured():
        try:
            telegram.send(body)
            results["telegram"] = "sent"
        except Exception as exc:  # noqa: BLE001
            results["telegram"] = f"failed: {exc}"
    if email.configured():
        try:
            email.send(
                subject,
                text,
                "<div style='font-family:Inter,Arial,sans-serif;white-space:pre-line'>" + body + "</div>",
            )
            results["email"] = "sent"
        except Exception as exc:  # noqa: BLE001
            results["email"] = f"failed: {exc}"
    for channel, outcome in results.items():
        (log.info if outcome == "sent" else log.warning)("Alert via %s: %s", channel, outcome)
    return results


def send_test(channel: str) -> str:
    message = "✅ <b>Ad Spy Engine</b> test alert — notifications are working."
    if channel == "telegram":
        telegram.send(message)
    elif channel == "email":
        email.send("Ad Spy Engine test alert", "Notifications are working.", f"<p>{message}</p>")
    else:
        raise ValueError(f"Unknown channel {channel}")
    return "sent"


def summarize(summary: dict[str, Any]) -> str:
    if summary.get("baseline"):
        return f"Baseline scan ({summary.get('ads', 0)} ads)"
    return f"{summary.get('new', 0)} new · {summary.get('stopped', 0)} stopped · {summary.get('scaled', 0)} scaled"
