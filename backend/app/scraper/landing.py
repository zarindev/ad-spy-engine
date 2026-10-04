"""Landing page capture: screenshot each distinct ad destination once (deduplicated by normalized URL)."""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections.abc import Callable
from datetime import timedelta
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from sqlmodel import Session, select

from app.core.config import get_selectors, get_settings
from app.db.models import LandingPage, utcnow
from app.scraper.driver import create_driver, safe_quit
from app.scraper.media import competitor_media_dir, relative_to_data

log = logging.getLogger(__name__)

TRACKING_PARAMS = (
    "utm_",
    "fbclid",
    "gclid",
    "mc_",
    "_hs",
    "ref",
    "srsltid",
    "campaign_id",
    "ad_id",
    "adset_id",
)
SKIP_HOSTS = (
    "facebook.com",
    "fb.me",
    "fb.com",
    "m.me",
    "instagram.com",
    "messenger.com",
    "whatsapp.com",
    "wa.me",
    "apps.apple.com",
    "play.google.com",
)
EXTRA_CONSENT = [
    "Accept",
    "Accept All",
    "Accept all cookies",
    "Accept Cookies",
    "I agree",
    "I Accept",
    "Agree",
    "Got it",
    "OK",
    "Allow all",
    "Allow All",
]


def url_key(url: str | None) -> str | None:
    """Normalize a destination so tracking-parameter variants share one capture."""
    if not url:
        return None
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    host = parsed.netloc.lower().removeprefix("www.")
    query = [(k, v) for k, v in parse_qsl(parsed.query) if not k.lower().startswith(TRACKING_PARAMS)]
    path = parsed.path.rstrip("/") or "/"
    return urlunparse(("https", host, path, "", urlencode(sorted(query)), ""))


def is_capturable(url: str | None) -> bool:
    key = url_key(url)
    if not key:
        return False
    host = urlparse(key).netloc
    return not any(host == h or host.endswith("." + h) for h in SKIP_HOSTS)


def _dismiss_banners(driver) -> None:  # noqa: ANN001
    labels = get_selectors().get("consent", {}).get("button_texts", []) + EXTRA_CONSENT
    for label in labels:
        xpath = (
            f'//button[normalize-space(.)="{label}"] | //a[@role=\'button\' and normalize-space(.)="{label}"]'
        )
        for el in driver.find_elements(By.XPATH, xpath)[:2]:
            try:
                if el.is_displayed():
                    el.click()
                    time.sleep(0.6)
                    return
            except WebDriverException:
                continue


def capture_one(driver, url: str, slug: str) -> LandingPage:  # noqa: ANN001
    key = url_key(url) or url
    page = LandingPage(url_key=key, url=url)
    try:
        try:
            driver.get(url)
        except TimeoutException:
            log.info("Landing page slow to load, capturing what rendered: %s", url)
        time.sleep(2.5)
        _dismiss_banners(driver)
        driver.execute_script("window.scrollTo(0, 0)")
        time.sleep(0.5)
        folder = competitor_media_dir(slug) / "landing"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{hashlib.sha1(key.encode()).hexdigest()[:14]}.png"
        driver.save_screenshot(str(path))
        page.screenshot_path = relative_to_data(path)
        page.final_url = driver.current_url
        page.title = (driver.title or "")[:300] or None
        page.status = "ok"
    except WebDriverException as exc:
        page.status, page.error = "failed", f"{type(exc).__name__}: {str(exc).splitlines()[0][:200]}"
        log.warning("Landing capture failed for %s: %s", url, page.error)
    page.captured_at = utcnow()
    return page


def capture_landing_pages(
    session: Session,
    urls: list[str],
    slug: str,
    cancel: threading.Event | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    max_age_days: int = 7,
) -> int:
    """Capture each distinct, not-recently-captured URL. Caller commits. Returns pages captured."""
    cfg = get_settings().get("landing", {})
    fresh_after = utcnow() - timedelta(days=max_age_days)
    todo: dict[str, str] = {}
    for url in urls:
        key = url_key(url)
        if not key or key in todo or not is_capturable(url):
            continue
        existing = session.exec(select(LandingPage).where(LandingPage.url_key == key)).first()
        if existing and existing.status == "ok" and existing.captured_at >= fresh_after:
            continue
        todo[key] = url
    if not todo:
        return 0

    driver = create_driver(headless=True, install_capture=False)
    driver.set_page_load_timeout(int(cfg.get("timeout", 25)))
    driver.set_window_size(1366, 900)
    done = 0
    try:
        for i, (key, url) in enumerate(todo.items(), 1):
            if cancel is not None and cancel.is_set():
                break
            captured = capture_one(driver, url, slug)
            existing = session.exec(select(LandingPage).where(LandingPage.url_key == key)).first()
            if existing:
                for field in (
                    "url",
                    "final_url",
                    "title",
                    "screenshot_path",
                    "status",
                    "error",
                    "captured_at",
                ):
                    setattr(existing, field, getattr(captured, field))
                session.add(existing)
            else:
                session.add(captured)
            session.commit()
            done += int(captured.status == "ok")
            if on_progress:
                on_progress(i, len(todo))
    finally:
        safe_quit(driver)
    log.info("Captured %d/%d landing pages", done, len(todo))
    return done


def landing_for(session: Session, url: str | None) -> LandingPage | None:
    key = url_key(url)
    if not key:
        return None
    return session.exec(select(LandingPage).where(LandingPage.url_key == key)).first()
