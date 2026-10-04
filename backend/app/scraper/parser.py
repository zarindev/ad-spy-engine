"""Pure parsing functions: page HTML / GraphQL payloads / ad-card HTML  ->  AdRecord.

Nothing in this module touches the network or a browser, so every function is unit-tested
offline against fixtures saved from the real Ad Library (backend/tests/fixtures/).

Two extraction strategies, merged per ad:
  * JSON  — the Ad Library ships each result as structured JSON, both server-rendered in
            <script type="application/json"> and in /api/graphql/ pagination responses.
  * DOM   — fallback that reads a rendered ad card using stable text anchors
            ("Library ID", "Started running on") instead of obfuscated class names.
"""

from __future__ import annotations

import json
import logging
import re
import zlib
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup, Tag
from dateutil import parser as dateparser

log = logging.getLogger(__name__)

PLACEHOLDER_TEXT = {"", " ", "​"}
MEDIA_TYPES = ("image", "video", "carousel", "dynamic", "catalog", "text")


@dataclass
class AdRecord:
    library_id: str
    page_name: str | None = None
    page_id: str | None = None
    page_profile_image: str | None = None
    page_profile_uri: str | None = None
    status: str = "active"
    start_date: date | None = None
    end_date: date | None = None
    days_running: int = 0
    platforms: list[str] = field(default_factory=list)
    ad_copy: str | None = None
    headline: str | None = None
    description: str | None = None
    cta_text: str | None = None
    cta_type: str | None = None
    landing_url: str | None = None
    display_format: str | None = None
    media_type: str = "image"
    media_urls: list[str] = field(default_factory=list)
    thumbnail_url: str | None = None
    variation_count: int = 1
    collation_id: str | None = None
    raw_html: str | None = None
    raw_json: dict[str, Any] | None = None
    source: str = "json"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("raw_html", None)
        data.pop("raw_json", None)
        return data


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):  # e.g. {"text": "..."}
        value = value.get("text")
    if not isinstance(value, str):
        return None
    text = value.replace("​", "").strip()
    return None if text in PLACEHOLDER_TEXT else text


def is_template_text(text: str | None) -> bool:
    """Catalog ads contain unrendered placeholders like "{{product.price}} | {{product.name}}"."""
    if not text or "{{" not in text:
        return False
    rest = re.sub(r"\{\{[^}]*\}\}", "", text)
    return not re.search(r"\w", rest)


def unwrap_redirect(url: str | None) -> str | None:
    """Turn https://l.facebook.com/l.php?u=<encoded>&h=... into the real destination."""
    if not url:
        return None
    url = url.strip()
    parsed = urlparse(url)
    if parsed.netloc.endswith("facebook.com") and parsed.path.startswith("/l.php"):
        target = parse_qs(parsed.query).get("u", [None])[0]
        if target:
            return unquote(target)
    return url


def compress(value: str | bytes | dict | None) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, dict):
        value = json.dumps(value, ensure_ascii=False)
    if isinstance(value, str):
        value = value.encode("utf-8")
    return zlib.compress(value, 6)


def decompress(blob: bytes | None) -> str | None:
    return zlib.decompress(blob).decode("utf-8") if blob else None


def parse_count(text: str) -> int | None:
    """'~1.2K' -> 1200, '1,234' -> 1234, '~120' -> 120."""
    raw = text.strip().lstrip("~").strip().replace(" ", "")
    mult = 1
    if raw[-1:].lower() == "k":
        mult, raw = 1_000, raw[:-1]
    elif raw[-1:].lower() == "m":
        mult, raw = 1_000_000, raw[:-1]
    if mult > 1:
        raw = raw.replace(",", ".")
        try:
            return int(float(raw) * mult)
        except ValueError:
            return None
    digits = re.sub(r"[^\d]", "", raw)
    return int(digits) if digits else None


def parse_total_results(text: str, patterns: Iterable[str]) -> int | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return parse_count(match.group(1))
    return None


# Month names for the locales listed in selectors.yaml -> English, so dateutil can parse.
_MONTHS = {
    "ene": "jan",
    "enero": "jan",
    "febrero": "feb",
    "marzo": "mar",
    "abr": "apr",
    "abril": "apr",
    "mayo": "may",
    "junio": "jun",
    "julio": "jul",
    "ago": "aug",
    "agosto": "aug",
    "septiembre": "sep",
    "sept": "sep",
    "set": "sep",
    "octubre": "oct",
    "noviembre": "nov",
    "dic": "dec",
    "diciembre": "dec",
    "janv": "jan",
    "janvier": "jan",
    "févr": "feb",
    "février": "feb",
    "mars": "mar",
    "avr": "apr",
    "avril": "apr",
    "mai": "may",
    "juin": "jun",
    "juil": "jul",
    "juillet": "jul",
    "août": "aug",
    "aout": "aug",
    "septembre": "sep",
    "octobre": "oct",
    "novembre": "nov",
    "déc": "dec",
    "décembre": "dec",
    "januar": "jan",
    "jän": "jan",
    "februar": "feb",
    "märz": "mar",
    "mär": "mar",
    "juni": "jun",
    "juli": "jul",
    "okt": "oct",
    "oktober": "oct",
    "dez": "dec",
    "dezember": "dec",
    "fev": "feb",
    "fevereiro": "feb",
    "março": "mar",
    "maio": "may",
    "out": "oct",
    "outubro": "oct",
    "dez.": "dec",
    "dezembro": "dec",
}


def parse_human_date(text: str | None) -> date | None:
    """Parse 'Oct 20, 2025', '20 Oct 2025', '20 oct. 2025', '20. Okt. 2025', '20 de oct de 2025'."""
    if not text:
        return None
    cleaned = text.strip().lower().replace("​", "")
    cleaned = re.sub(r"\bde\b", " ", cleaned)
    tokens = re.split(r"(\s+|,)", cleaned)
    tokens = [_MONTHS.get(t.strip("."), _MONTHS.get(t, t)) for t in tokens]
    cleaned = re.sub(r"(?<=\d)\.", " ", "".join(tokens))
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,")
    try:
        return dateparser.parse(cleaned, fuzzy=True, default=datetime(2000, 1, 1)).date()
    except (ValueError, OverflowError):
        log.debug("Unparseable date text: %r", text)
        return None


def compute_days_running(start: date | None, end: date | None, active: bool, today: date) -> int:
    if not start:
        return 0
    stop = today if active or not end else min(end, today)
    return max((stop - start).days, 0) + 1  # an ad that started today has run 1 day


def from_timestamp(ts: Any) -> date | None:
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=UTC).date()
    except (TypeError, ValueError, OSError):
        return None


# --------------------------------------------------------------------------------------
# JSON extraction
# --------------------------------------------------------------------------------------


def iter_ad_nodes(obj: Any, marker: str = "ad_archive_id") -> Iterator[dict[str, Any]]:
    """Depth-first walk yielding every dict that looks like one ad result."""
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            if marker in cur and isinstance(cur.get("snapshot"), dict):
                yield cur
                continue
            stack.extend(reversed(list(cur.values())))
        elif isinstance(cur, list):
            stack.extend(reversed(cur))


def find_key(obj: Any, key: str) -> Any:
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            if key in cur:
                return cur[key]
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return None


def parse_json_payload(text: str) -> list[Any]:
    """GraphQL responses may be prefixed with `for (;;);` and/or be newline-delimited JSON."""
    text = text.strip()
    if text.startswith("for (;;);"):
        text = text[len("for (;;);") :]
    try:
        return [json.loads(text)]
    except json.JSONDecodeError:
        pass
    docs = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            docs.append(json.loads(line))
        except json.JSONDecodeError:
            log.debug("Skipping non-JSON line in payload (%d chars)", len(line))
    return docs


def extract_page_json_docs(html: str, markers: Iterable[str] = ("ad_archive_id",)) -> list[Any]:
    """All server-rendered JSON blobs in a page that mention any of the marker keys."""
    soup = BeautifulSoup(html, "lxml")
    docs = []
    for script in soup.find_all("script", attrs={"type": "application/json"}):
        body = script.string or script.get_text()
        if body and any(m in body for m in markers):
            docs.extend(parse_json_payload(body))
    return docs


def extract_nodes_from_html(html: str) -> list[dict[str, Any]]:
    return [n for doc in extract_page_json_docs(html) for n in iter_ad_nodes(doc)]


def extract_nodes_from_payload(text: str) -> list[dict[str, Any]]:
    return [n for doc in parse_json_payload(text) for n in iter_ad_nodes(doc)]


def extract_connection_meta(html_or_docs: str | list[Any]) -> dict[str, Any]:
    """Total count + captcha flag from the server-rendered page data."""
    docs = (
        extract_page_json_docs(
            html_or_docs, ("search_results_connection", "xfb_ad_library_is_captcha_required")
        )
        if isinstance(html_or_docs, str)
        else html_or_docs
    )
    meta: dict[str, Any] = {"count": None, "captcha_required": False}
    for doc in docs:
        conn = find_key(doc, "search_results_connection")
        if isinstance(conn, dict) and conn.get("count") is not None:
            meta["count"] = conn["count"]
        if find_key(doc, "xfb_ad_library_is_captcha_required") is True:
            meta["captcha_required"] = True
    return meta


def _media_type_from_snapshot(fmt: str | None, snap: dict[str, Any]) -> str:
    cards = snap.get("cards") or []
    has_video = bool(snap.get("videos")) or any(c.get("video_hd_url") or c.get("video_sd_url") for c in cards)
    fmt = (fmt or "").upper()
    if fmt == "VIDEO" or (fmt in {"DCO", "DPA"} and has_video):
        return "video"
    if fmt in {"CAROUSEL", "MULTI_IMAGES"}:
        return "carousel"
    if fmt == "DPA":
        return "catalog"
    if fmt == "DCO":
        return "dynamic"
    if fmt == "TEXT" or (not snap.get("images") and not cards and not has_video):
        return "text"
    return "image"


def _collect_media(snap: dict[str, Any]) -> tuple[list[str], str | None]:
    urls: list[str] = []
    thumb: str | None = None

    def add(url: str | None) -> None:
        if url and url not in urls:
            urls.append(url)

    for video in (snap.get("videos") or []) + (snap.get("extra_videos") or []):
        add(video.get("video_hd_url") or video.get("video_sd_url"))
        thumb = thumb or video.get("video_preview_image_url")
    for image in (snap.get("images") or []) + (snap.get("extra_images") or []):
        add(image.get("original_image_url") or image.get("resized_image_url"))
        thumb = thumb or image.get("resized_image_url") or image.get("original_image_url")
    for card in snap.get("cards") or []:
        add(card.get("video_hd_url") or card.get("video_sd_url"))
        add(card.get("original_image_url") or card.get("resized_image_url"))
        thumb = (
            thumb
            or card.get("video_preview_image_url")
            or card.get("resized_image_url")
            or card.get("original_image_url")
        )
    return urls, thumb


def record_from_node(node: dict[str, Any], today: date | None = None) -> AdRecord:
    """Map one Ad Library JSON result to an AdRecord."""
    today = today or datetime.now(UTC).date()
    snap = node.get("snapshot") or {}
    cards = snap.get("cards") or []
    first_card = cards[0] if cards else {}
    fmt = snap.get("display_format")

    def pick(key: str, alt_key: str | None = None) -> str | None:
        """Top-level text, falling back to the first card when blank or an unrendered template."""
        for source in (snap, first_card):
            value = clean_text(source.get(key)) or (clean_text(source.get(alt_key)) if alt_key else None)
            if value and not is_template_text(value):
                return value
        return None

    copy = pick("body")
    headline = pick("title")
    description = pick("link_description")
    landing = snap.get("link_url") or first_card.get("link_url")
    cta_text = pick("cta_text")
    cta_type = snap.get("cta_type") or first_card.get("cta_type")

    active = bool(node.get("is_active", True))
    start = from_timestamp(node.get("start_date"))
    end = from_timestamp(node.get("end_date"))
    media_urls, thumb = _collect_media(snap)

    # "N ads use this creative and text" -> collation_count; DCO "multiple versions" -> cards.
    versions = len(cards) if (fmt or "").upper() == "DCO" else 1
    variation_count = max(int(node.get("collation_count") or 1), versions, 1)

    platforms = [str(p).upper() for p in node.get("publisher_platform") or []]

    return AdRecord(
        library_id=str(node.get("ad_archive_id")),
        page_name=clean_text(snap.get("page_name")) or clean_text(node.get("page_name")),
        page_id=str(node.get("page_id") or snap.get("page_id") or "") or None,
        page_profile_image=snap.get("page_profile_picture_url"),
        page_profile_uri=snap.get("page_profile_uri"),
        status="active" if active else "inactive",
        start_date=start,
        end_date=None if active else end,
        days_running=compute_days_running(start, end, active, today),
        platforms=platforms,
        ad_copy=copy,
        headline=headline,
        description=description,
        cta_text=cta_text,
        cta_type=cta_type,
        landing_url=unwrap_redirect(landing),
        display_format=fmt,
        media_type=_media_type_from_snapshot(fmt, snap),
        media_urls=media_urls,
        thumbnail_url=thumb,
        variation_count=variation_count,
        collation_id=str(node["collation_id"]) if node.get("collation_id") else None,
        raw_json=node,
        source="json",
    )


# --------------------------------------------------------------------------------------
# DOM fallback (text anchors only)
# --------------------------------------------------------------------------------------


def _first_match(patterns: Iterable[str], text: str) -> re.Match[str] | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match
    return None


def find_card_roots(html: str, anchor_patterns: Iterable[str]) -> list[Tag]:
    """Card root = highest ancestor of a 'Library ID' text node that contains exactly one ID."""
    soup = BeautifulSoup(html, "lxml")
    patterns = [re.compile(p, re.IGNORECASE) for p in anchor_patterns]

    def has_id(s: str | None) -> bool:
        return bool(s) and any(p.search(s) for p in patterns)  # type: ignore[arg-type]

    roots: list[Tag] = []
    for node in soup.find_all(string=has_id):
        root = node.parent
        if root is None:
            continue
        while root.parent is not None and len(root.parent.find_all(string=has_id)) == 1:
            root = root.parent
        if not any(root is r for r in roots):
            roots.append(root)
    return roots


def record_from_card_html(html: str, selectors: dict[str, Any], today: date | None = None) -> AdRecord | None:
    """Best-effort parse of one rendered ad card. Returns None when no Library ID is found."""
    today = today or datetime.now(UTC).date()
    anchors = selectors.get("anchors", {})
    soup = BeautifulSoup(html, "lxml")
    strings = [s.replace("​", "").strip() for s in soup.stripped_strings]
    strings = [s for s in strings if s]
    full = "\n".join(strings)

    id_match = _first_match(anchors.get("library_id", [r"Library ID:?\s*(\d+)"]), full)
    if not id_match:
        return None
    rec = AdRecord(library_id=id_match.group(1), source="dom", raw_html=html)

    inactive_words = {w.lower() for w in anchors.get("status_inactive", ["Inactive"])}
    rec.status = "inactive" if any(s.lower() in inactive_words for s in strings[:6]) else "active"

    for line in strings:
        started = _first_match(anchors.get("started_running", []), line)
        if started:
            rec.start_date = parse_human_date(started.group(1))
            break
        rng = re.fullmatch(anchors.get("date_range", r"(.+?)\s+[-–]\s+(.+)"), line)
        if rng and parse_human_date(rng.group(1)) and parse_human_date(rng.group(2)):
            rec.start_date = parse_human_date(rng.group(1))
            rec.end_date = parse_human_date(rng.group(2))
            break
    rec.days_running = compute_days_running(rec.start_date, rec.end_date, rec.status == "active", today)

    var_match = _first_match(anchors.get("variations", []), full)
    if var_match:
        rec.variation_count = int(var_match.group(1)) if var_match.groups() else 2

    # Platforms (best effort; Facebook's own icon is not a sprite and can't be detected).
    sprites = selectors.get("platform_sprites", {})
    for el in soup.find_all(style=re.compile("mask-position")):
        pos = re.search(r"mask-position:\s*([^;]+)", el["style"])
        name = sprites.get(pos.group(1).strip()) if pos else None
        if name and name not in rec.platforms:
            rec.platforms.append(name)

    # Page name / link: first anchor pointing at a facebook.com profile.
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(" ", strip=True)
        if "facebook.com/" in href and "/l.php" not in href and text and not rec.page_name:
            rec.page_name, rec.page_profile_uri = text, href
        elif not rec.landing_url and ("/l.php" in href or "facebook.com" not in href):
            rec.landing_url = unwrap_redirect(href)
    if not rec.landing_url:  # e.g. marketplace or on-Facebook destinations
        links = [a["href"] for a in soup.find_all("a", href=True) if a.get_text(strip=True)]
        rec.landing_url = links[-1] if len(links) > 1 else None

    # Ad copy: the longest text segment after "Sponsored".
    sponsored = {w.lower() for w in anchors.get("sponsored", ["Sponsored"])}
    after = next((i for i, s in enumerate(strings) if s.lower() in sponsored), None)
    body_lines = strings[after + 1 :] if after is not None else strings
    cta_set = {c.lower() for c in selectors.get("cta_texts", [])}
    for line in reversed(body_lines):
        if line.lower() in cta_set:
            rec.cta_text = line
            break
    candidates = [s for s in body_lines if s.lower() not in cta_set and s != rec.page_name]
    if candidates:
        rec.ad_copy = max(candidates, key=len)

    # Media.
    profile_alt = (rec.page_name or "").strip()
    for img in soup.find_all("img"):
        src = str(img.get("src") or "")
        if not src or src.startswith("data:"):
            continue
        if str(img.get("alt") or "").strip() == profile_alt and profile_alt:
            rec.page_profile_image = rec.page_profile_image or src
            continue
        rec.media_urls.append(src)
    for video in soup.find_all("video"):
        if video.get("src"):
            rec.media_urls.insert(0, video["src"])
        rec.thumbnail_url = rec.thumbnail_url or video.get("poster")
        rec.media_type = "video"
    imgs = [u for u in rec.media_urls if "video" not in u]
    rec.thumbnail_url = rec.thumbnail_url or (imgs[0] if imgs else None)
    if rec.media_type != "video":
        rec.media_type = "carousel" if len(imgs) > 1 else ("image" if imgs else "text")
    return rec


def merge_records(primary: AdRecord | None, fallback: AdRecord | None) -> AdRecord | None:
    """Prefer JSON values, fill blanks from the DOM parse, keep the DOM's raw HTML."""
    if primary is None:
        return fallback
    if fallback is None:
        return primary
    for key, value in vars(fallback).items():
        current = getattr(primary, key)
        if key == "raw_html":
            primary.raw_html = value
        elif current in (None, "", []) and value not in (None, "", []):
            setattr(primary, key, value)
    primary.source = "json+dom"
    return primary


def matches_page(record: AdRecord, query: str) -> bool:
    """Used for keyword scans with exact_page: keep ads whose page name contains the query."""
    norm = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())  # noqa: E731
    return bool(norm(query)) and norm(query) in norm(record.page_name)
