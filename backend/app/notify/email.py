"""Email alerts over SMTP (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_TO)."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import env


def configured() -> bool:
    return bool(env("SMTP_HOST") and env("SMTP_TO"))


def send(subject: str, text: str, html: str | None = None, timeout: float = 20.0) -> None:
    host = env("SMTP_HOST")
    recipients = [r.strip() for r in (env("SMTP_TO") or "").split(",") if r.strip()]
    if not host or not recipients:
        raise RuntimeError("Email is not configured (set SMTP_HOST and SMTP_TO)")
    port = int(env("SMTP_PORT") or 587)
    user, password = env("SMTP_USER"), env("SMTP_PASSWORD")
    sender = env("SMTP_FROM") or user or "ad-spy-engine@localhost"

    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, sender, ", ".join(recipients)
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    context = ssl.create_default_context()
    if port == 465:
        server: smtplib.SMTP = smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)
    else:
        server = smtplib.SMTP(host, port, timeout=timeout)
    try:
        server.ehlo()
        if port != 465 and (env("SMTP_STARTTLS") or "true").lower() != "false":
            server.starttls(context=context)
            server.ehlo()
        if user and password:
            server.login(user, password)
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except smtplib.SMTPException:
            pass
