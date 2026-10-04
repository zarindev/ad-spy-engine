"""Meta Ad Library navigation: open search, dismiss consent, detect blocking, scroll, collect ads.

The scraper never logs in and never attempts to solve or bypass a captcha: when Meta shows a
login wall or challenge, the scan stops with status `blocked` and a human-readable reason.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, TypeVar
from urllib.parse import quote_plus

from selenium.common.exceptions import (
    JavascriptException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from app.core.config import get_selectors, get_settings
from app.scraper import humanize
from app.scraper.driver import create_driver, safe_quit
from app.scraper.parser import (
    AdRecord,
    extract_connection_meta,
    extract_nodes_from_html,
    extract_nodes_from_payload,
    find_key,
    matches_page,
    merge_records,
    parse_json_payload,
    parse_total_results,
    record_from_card_html,
    record_from_node,
)

log = logging.getLogger(__name__)
T = TypeVar("T")

PLATFORM_PARAMS = {
    "facebook": "facebook",
    "instagram": "instagram",
    "messenger": "messenger",
    "audience_network": "audience_network",
    "threads": "threads",
    "whatsapp": "whatsapp",
}
MEDIA_PARAMS = {"all", "image", "video", "meme", "image_and_meme", "none"}

BLOCK_SUGGESTIONS = [
    "Wait 15–30 minutes before scanning again (Meta rate-limits bursts of traffic).",
    "Switch to visible mode in Settings so you can see what Meta is showing.",
    "Try the undetected driver (Settings → Scraping → Driver).",
    "Lower max ads or raise the delay range in Settings.",
]

# Finds rendered ad cards that have not been processed yet. A card root is the highest
# ancestor of a "Library ID" text node that still contains exactly one such label.
FIND_CARDS_JS = r"""
const anchor = arguments[0];
const re = new RegExp(arguments[1], 'i');
const count = (el) => (el.textContent.split(anchor).length - 1);
const out = [];
const snap = document.evaluate(`//*[text()[contains(., '${anchor}')]]`, document, null,
                               XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
for (let i = 0; i < snap.snapshotLength; i++) {
  const label = snap.snapshotItem(i);
  const m = label.textContent.match(re);
  if (!m) continue;
  let root = label;
  while (root.parentElement && count(root.parentElement) === 1) root = root.parentElement;
  if (root.dataset.adspyDone) continue;
  root.dataset.adspyDone = '1';
  out.push({id: m[1], html: root.outerHTML, el: root});
}
return out;
"""

# Sticky/fixed overlays (search bar, filter chips) would otherwise be baked into card screenshots.
TOGGLE_OVERLAYS_JS = r"""
const hide = arguments[0];
if (hide) {
  for (const el of document.querySelectorAll('body *')) {
    const pos = getComputedStyle(el).position;
    if ((pos === 'fixed' || pos === 'sticky') && !el.dataset.adspyDone && !el.closest('[data-adspy-done]')) {
      el.dataset.adspyHidden = el.style.visibility || '-';
      el.style.visibility = 'hidden';
    }
  }
} else {
  for (const el of document.querySelectorAll('[data-adspy-hidden]')) {
    el.style.visibility = el.dataset.adspyHidden === '-' ? '' : el.dataset.adspyHidden;
    delete el.dataset.adspyHidden;
  }
}
"""

IMAGES_READY_JS = r"""
const el = arguments[0];
return Array.from(el.querySelectorAll('img')).every(i => i.complete && i.naturalWidth > 0);
"""


class ScanBlocked(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.suggestions = BLOCK_SUGGESTIONS


class ScanCancelled(Exception):
    pass


@dataclass
class ScanParams:
    query: str
    search_type: str = "keyword"  # keyword | page_id
    country: str = "US"
    media_type: str = "all"
    platforms: list[str] = field(default_factory=list)
    active_status: str = "active"  # active | inactive | all
    max_ads: int = 200
    exact_page: bool = False
    headless: bool | None = None
    driver_type: str | None = None


@dataclass
class ScanStats:
    total_results: int | None = None
    found: int = 0
    processed: int = 0
    failed: int = 0
    filtered_out: int = 0
    scrolls: int = 0
    stop_reason: str = ""
    page_ids: dict[str, str] = field(default_factory=dict)  # page_id -> page_name


EventFn = Callable[[str, dict[str, Any]], None]
AdFn = Callable[[AdRecord, bytes | None], None]


def build_search_url(params: ScanParams, selectors: dict[str, Any] | None = None) -> str:
    sel = (selectors or get_selectors())["url"]
    media = params.media_type if params.media_type in MEDIA_PARAMS else "all"
    if params.media_type in {"carousel"}:
        media = "all"  # the Ad Library has no carousel filter; filtered after parsing
    common = {
        "status": params.active_status or "active",
        "country": (params.country or "ALL").upper(),
        "media": media,
    }
    if params.search_type == "page_id":
        path = sel["page_id"].format(page_id=quote_plus(params.query.strip()), **common)
    else:
        path = sel["keyword"].format(query=quote_plus(params.query.strip()), **common)
    url = sel["base"] + path
    platforms = [PLATFORM_PARAMS[p.lower()] for p in params.platforms if p.lower() in PLATFORM_PARAMS]
    for i, platform in enumerate(platforms):
        url += "&" + sel["platform_param"].format(i=i, platform=platform)
    return url


def with_retries(
    fn: Callable[[], T],
    attempts: int = 3,
    base_delay: float = 1.0,
    retry_on: tuple[type[BaseException], ...] = (
        StaleElementReferenceException,
        TimeoutException,
        JavascriptException,
    ),
) -> T:
    """Exponential backoff for transient Selenium errors."""
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except retry_on as exc:
            if attempt == attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            log.debug("Retry %d/%d after %s: %s", attempt, attempts, type(exc).__name__, exc)
            time.sleep(delay)
    raise RuntimeError("unreachable")


class AdLibraryScraper:
    def __init__(
        self,
        params: ScanParams,
        on_event: EventFn | None = None,
        cancel: threading.Event | None = None,
    ) -> None:
        self.params = params
        self.settings = get_settings().get("scraping", {})
        self.selectors = get_selectors()
        self.on_event = on_event or (lambda _t, _d: None)
        self.cancel = cancel or threading.Event()
        self.stats = ScanStats()
        self.driver: Any = None
        self._json_nodes: dict[str, dict[str, Any]] = {}
        self._has_next_page: bool | None = None
        self.today = datetime.now(UTC).date()

    # ----------------------------------------------------------------- helpers
    def emit(self, kind: str, **data: Any) -> None:
        try:
            self.on_event(kind, data)
        except Exception:  # noqa: BLE001 — a UI callback must never break a scan
            log.exception("Event callback failed")

    def info(self, message: str, *args: Any) -> None:
        text = message % args if args else message
        log.info(text)
        self.emit("log", level="info", message=text)

    def warn(self, message: str, *args: Any) -> None:
        text = message % args if args else message
        log.warning(text)
        self.emit("log", level="warning", message=text)

    def check_cancel(self) -> None:
        if self.cancel.is_set():
            raise ScanCancelled("Scan cancelled by user")

    def body_text(self) -> str:
        try:
            return self.driver.find_element(By.TAG_NAME, "body").text or ""
        except WebDriverException:
            return ""

    # ----------------------------------------------------------------- page state
    def detect_block(self, text: str | None = None) -> str | None:
        block = self.selectors.get("blocking", {})
        url = (self.driver.current_url or "").lower()
        for fragment in block.get("url_contains", []):
            if fragment.lower() in url:
                return f"Redirected to a restricted page ({fragment.strip('/')}) — Meta is asking for a login or check."
        text = text if text is not None else self.body_text()
        lowered = text.lower()
        for phrase in block.get("page_texts", []):
            if phrase.lower() in lowered:
                return f"Meta displayed: “{phrase}”."
        return None

    def has_error_banner(self, text: str) -> str | None:
        lowered = text.lower()
        for phrase in self.selectors.get("blocking", {}).get("error_banners", []):
            if phrase.lower() in lowered:
                return phrase
        return None

    def has_no_results(self, text: str) -> bool:
        lowered = text.lower()
        return any(p.lower() in lowered for p in self.selectors["anchors"].get("no_results", []))

    def dismiss_consent(self) -> bool:
        for label in self.selectors.get("consent", {}).get("button_texts", []):
            xpath = (
                f"//*[(@role='button' or self::button) and "
                f'(normalize-space(.)="{label}" or @aria-label="{label}")]'
            )
            for el in self.driver.find_elements(By.XPATH, xpath):
                try:
                    if el.is_displayed():
                        el.click()
                        self.info("Dismissed consent dialog (“%s”)", label)
                        time.sleep(1.0)
                        return True
                except WebDriverException:
                    continue
        return False

    # ----------------------------------------------------------------- collection
    def _ingest_nodes(self, nodes: list[dict[str, Any]]) -> None:
        for node in nodes:
            lid = str(node.get("ad_archive_id"))
            self._json_nodes.setdefault(lid, node)

    def drain_captured_json(self) -> None:
        try:
            payloads = (
                self.driver.execute_script("return (window.__adspy || []).splice(0, window.__adspy.length);")
                or []
            )
        except WebDriverException:
            payloads = []
        for payload in payloads:
            for doc in parse_json_payload(payload):
                conn = find_key(doc, "search_results_connection")
                if isinstance(conn, dict):
                    info = conn.get("page_info") or {}
                    if "has_next_page" in info:
                        self._has_next_page = bool(info["has_next_page"])
            self._ingest_nodes(extract_nodes_from_payload(payload))

    def screenshot_card(self, element: WebElement) -> bytes | None:
        if not self.settings.get("screenshots", True):
            return None

        def shoot() -> bytes:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'start', inline: 'nearest'});", element
            )
            deadline = time.time() + 2.5
            while time.time() < deadline:
                if self.driver.execute_script(IMAGES_READY_JS, element):
                    break
                time.sleep(0.2)
            return element.screenshot_as_png

        try:
            return with_retries(shoot, attempts=int(self.settings.get("retries", 3)), base_delay=0.5)
        except WebDriverException as exc:
            log.warning("Screenshot failed: %s", exc.__class__.__name__)
            return None

    def process_new_cards(self, on_ad: AdFn) -> int:
        anchor = self.selectors["anchors"].get("card_xpath_anchor", "Library ID")
        id_regex = self.selectors["anchors"]["library_id"][0]
        cards = with_retries(
            lambda: self.driver.execute_script(FIND_CARDS_JS, anchor, id_regex) or [],
            attempts=int(self.settings.get("retries", 3)),
        )
        new = 0
        if cards and self.settings.get("screenshots", True):
            self._toggle_overlays(True)
        try:
            new = self._process_cards(cards, on_ad)
        finally:
            if cards and self.settings.get("screenshots", True):
                self._toggle_overlays(False)
        return new

    def _toggle_overlays(self, hide: bool) -> None:
        try:
            self.driver.execute_script(TOGGLE_OVERLAYS_JS, hide)
        except WebDriverException as exc:
            log.debug("Overlay toggle failed: %s", exc)

    def _process_cards(self, cards: list[dict[str, Any]], on_ad: AdFn) -> int:
        new = 0
        for card in cards:
            if self.stats.found >= self.params.max_ads:
                break
            self.check_cancel()
            new += 1
            lid = str(card.get("id"))
            try:
                node = self._json_nodes.pop(lid, None)
                json_rec = record_from_node(node, self.today) if node else None
                dom_rec = record_from_card_html(card.get("html", ""), self.selectors, self.today)
                record = merge_records(json_rec, dom_rec)
                if record is None:
                    raise ValueError("card had no parseable Library ID")
                if not self._accept(record):
                    continue
                if node is None:
                    log.warning("Ad %s parsed from DOM only (no JSON captured)", lid)
                self.stats.found += 1
                png = self.screenshot_card(card["el"])
                on_ad(record, png)
                self.stats.processed += 1
            except ScanCancelled:
                raise
            except Exception as exc:  # noqa: BLE001 — one bad ad never kills the scan
                self.stats.failed += 1
                log.warning("Failed to process ad %s: %s", lid, exc, exc_info=True)
                self.emit("ad_failed", library_id=lid, error=str(exc))
            self.emit_progress()
        return new

    def _accept(self, record: AdRecord) -> bool:
        if record.page_id and record.page_name:
            self.stats.page_ids.setdefault(record.page_id, record.page_name)
        if self.params.media_type == "carousel" and record.media_type != "carousel":
            self.stats.filtered_out += 1
            return False
        if (
            self.params.search_type == "keyword"
            and self.params.exact_page
            and not matches_page(record, self.params.query)
        ):
            self.stats.filtered_out += 1
            return False
        return True

    def process_leftover_json(self, on_ad: AdFn) -> None:
        """Ads present in captured JSON that never rendered as a card (no screenshot)."""
        for lid, node in list(self._json_nodes.items()):
            if self.stats.found >= self.params.max_ads:
                break
            self._json_nodes.pop(lid, None)
            try:
                record = record_from_node(node, self.today)
                if not self._accept(record):
                    continue
                self.stats.found += 1
                on_ad(record, None)
                self.stats.processed += 1
            except Exception as exc:  # noqa: BLE001
                self.stats.failed += 1
                log.warning("Failed to process JSON-only ad %s: %s", lid, exc)
        self.emit_progress()

    def emit_progress(self) -> None:
        self.emit(
            "progress",
            total=self.stats.total_results,
            found=self.stats.found,
            processed=self.stats.processed,
            failed=self.stats.failed,
            max_ads=self.params.max_ads,
        )

    # ----------------------------------------------------------------- main loop
    def open_search(self) -> None:
        url = build_search_url(self.params, self.selectors)
        self.info("Opening Ad Library: %s", url)

        def load() -> None:
            self.driver.get(url)

        with_retries(
            load,
            attempts=int(self.settings.get("retries", 3)),
            base_delay=3.0,
            retry_on=(TimeoutException, WebDriverException),
        )
        humanize.sleep_range(self.settings.get("initial_wait", [4, 7]), self.cancel)
        self.check_cancel()
        self.dismiss_consent()

    def read_initial_state(self) -> None:
        html = self.driver.page_source
        meta = extract_connection_meta(html)
        if meta["captcha_required"]:
            raise ScanBlocked("Meta is requiring a captcha for the Ad Library right now.")
        reason = self.detect_block()
        if reason:
            raise ScanBlocked(reason)
        self._ingest_nodes(extract_nodes_from_html(html))
        text = self.body_text()
        total = meta["count"]
        if total is None:
            total = parse_total_results(text, self.selectors["anchors"].get("total_results", []))
        self.stats.total_results = total
        self.info("Meta reports %s results", f"~{total}" if total is not None else "an unknown number of")
        self.emit_progress()

    def run(self, on_ad: AdFn) -> ScanStats:
        cfg = self.settings
        started = time.time()
        try:
            self.emit("status", status="starting_browser")
            self.driver = create_driver(self.params.headless, self.params.driver_type)
            self.emit("status", status="loading")
            self.open_search()
            self.read_initial_state()
            self.emit("status", status="scrolling")

            idle = 0
            max_idle = int(cfg.get("no_new_ads_attempts", 4))
            while True:
                self.check_cancel()
                self.drain_captured_json()
                new = self.process_new_cards(on_ad)
                if self.stats.found >= self.params.max_ads:
                    self.stats.stop_reason = "max_ads reached"
                    break
                if new:
                    idle = 0
                else:
                    idle += 1
                    text = self.body_text()
                    reason = self.detect_block(text)
                    if reason:
                        raise ScanBlocked(reason)
                    if self.stats.found == 0 and self.has_no_results(text):
                        self.stats.stop_reason = "no results"
                        break
                    banner = self.has_error_banner(text)
                    if banner and self.stats.found == 0 and idle >= 2:
                        raise ScanBlocked(f"Meta showed an error banner: “{banner}”.")
                    if self._has_next_page is False and idle >= 2:
                        self.stats.stop_reason = "end of results"
                        break
                    if idle >= max_idle:
                        self.stats.stop_reason = f"no new ads after {max_idle} scrolls"
                        break
                self.scroll(idle)
                self.stats.scrolls += 1
                humanize.sleep_range(cfg.get("delay_range", [1.2, 3.2]), self.cancel)
                humanize.maybe_long_pause(
                    float(cfg.get("long_pause_chance", 0.08)),
                    cfg.get("long_pause_range", [4, 8]),
                    self.cancel,
                )

            self.drain_captured_json()
            self.process_leftover_json(on_ad)
            self.info(
                "Finished: %d ads (%d failed, %d filtered) in %.0fs — %s",
                self.stats.found,
                self.stats.failed,
                self.stats.filtered_out,
                time.time() - started,
                self.stats.stop_reason,
            )
            return self.stats
        finally:
            if self.driver is not None:
                safe_quit(self.driver)
                self.driver = None

    def scroll(self, idle: int) -> None:
        try:
            if idle >= 1:
                # Nothing new: make sure we actually hit the bottom to trigger the next page.
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            else:
                humanize.human_scroll(
                    self.driver, humanize.scroll_distance(self.settings.get("scroll_step_px", [1400, 2600]))
                )
        except WebDriverException as exc:
            log.debug("Scroll failed: %s", exc)
