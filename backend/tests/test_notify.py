from __future__ import annotations

from types import SimpleNamespace

import pytest

from app import notify
from app.db.models import Ad, AdSnapshot, ChangeEvent, Competitor, Scan
from app.db.session import session_scope
from app.notify import email, telegram


def test_build_alert_lists_changes(migrated_db):
    with session_scope() as s:
        comp = Competitor(name="Alert <Brand>", slug="alert-brand")
        s.add(comp)
        s.flush()
        scan = Scan(
            competitor_id=comp.id,
            query="q",
            status="completed",
            change_summary={"new": 2, "stopped": 1, "scaled": 0, "still_running": 5},
        )
        s.add(scan)
        s.flush()
        ad = Ad(library_id="44000001", competitor_id=comp.id, headline="Huge summer sale", score=81)
        s.add(ad)
        s.flush()
        s.add(AdSnapshot(ad_id=ad.id, scan_id=scan.id))
        s.add(ChangeEvent(competitor_id=comp.id, scan_id=scan.id, ad_id=ad.id, kind="new"))
        s.commit()
        subject, text, html = notify.build_alert(s, scan)
    assert "2 new · 1 stopped · 0 scaled" in subject
    assert "Alert &lt;Brand&gt;" in html  # escaped for Telegram HTML
    assert "[NEW] score 81" in html and "Huge summer sale" in text
    assert f"/scans/{scan.id}" in text


def test_telegram_send(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    calls = []

    def fake_post(url, json, timeout):
        calls.append((url, json))
        return SimpleNamespace(
            status_code=200, headers={"content-type": "application/json"}, json=lambda: {"ok": True}, text=""
        )

    monkeypatch.setattr(telegram.httpx, "post", fake_post)
    telegram.send("<b>hi</b>")
    assert calls[0][0].endswith("/bot123:abc/sendMessage")
    assert calls[0][1]["chat_id"] == "42" and calls[0][1]["parse_mode"] == "HTML"

    monkeypatch.setattr(
        telegram.httpx,
        "post",
        lambda *a, **k: SimpleNamespace(
            status_code=401,
            headers={"content-type": "application/json"},
            json=lambda: {"ok": False, "description": "Unauthorized"},
            text="",
        ),
    )
    with pytest.raises(RuntimeError, match="Unauthorized"):
        telegram.send("x")


def test_email_send(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("SMTP_TO", "a@x.com, b@x.com")
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            sent["host"] = (host, port)

        def ehlo(self):
            pass

        def starttls(self, context):
            sent["tls"] = True

        def login(self, u, p):
            sent["login"] = u

        def send_message(self, msg):
            sent["to"] = msg["To"]
            sent["subject"] = msg["Subject"]

        def quit(self):
            pass

    monkeypatch.setattr(email.smtplib, "SMTP", FakeSMTP)
    email.send("Subj", "text", "<p>html</p>")
    assert sent == {
        "host": ("smtp.test", 587),
        "tls": True,
        "login": "u",
        "to": "a@x.com, b@x.com",
        "subject": "Subj",
    }


def test_unconfigured_channels(monkeypatch):
    for var in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "SMTP_HOST", "SMTP_TO"):
        monkeypatch.delenv(var, raising=False)
    assert notify.channels() == {"telegram": False, "email": False}
    with pytest.raises(RuntimeError):
        telegram.send("x")
