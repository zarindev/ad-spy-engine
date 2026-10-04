"""HTML report builder (Phase 1: single-competitor scan report; PDF/branding come in Phase 5)."""

from __future__ import annotations

import base64
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlmodel import select

from app.analysis.scoring import BADGES
from app.core.config import get_settings
from app.core.paths import TEMPLATES_DIR, data_dir, reports_dir, slugify
from app.db.models import Ad, AdSnapshot, Competitor, Scan
from app.db.session import session_scope


def jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["thousands"] = lambda n: f"{n:,}" if isinstance(n, int) else n
    return env


def image_data_uri(relative: str | None) -> str | None:
    """Embed local images so the report is a single portable file."""
    if not relative:
        return None
    path = data_dir() / relative
    if not path.exists():
        return None
    mime = "image/png" if path.suffix == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


DEFAULT_SECTIONS = ["summary", "charts", "top_ads", "all_ads"]


def scan_report_context(
    scan_id: int, top_n: int = 30, sections: list[str] | None = None, title: str | None = None
) -> dict[str, Any]:
    with session_scope() as session:
        scan = session.get(Scan, scan_id)
        if scan is None:
            raise ValueError(f"Scan {scan_id} not found")
        competitor = session.get(Competitor, scan.competitor_id)
        ads = session.exec(
            select(Ad)
            .join(AdSnapshot, AdSnapshot.ad_id == Ad.id)
            .where(AdSnapshot.scan_id == scan_id)
            .order_by(Ad.score.desc(), Ad.days_running.desc())  # type: ignore[attr-defined]
        ).all()

    badges = Counter((a.score_breakdown or {}).get("badge", "testing") for a in ads)
    formats = Counter(a.media_type for a in ads)
    platforms = Counter(p for a in ads for p in a.platforms or [])
    avg_days = round(sum(a.days_running for a in ads) / len(ads), 1) if ads else 0
    top = [
        {
            "ad": a,
            "badge": BADGES[(a.score_breakdown or {}).get("badge", "testing")],
            "badge_key": (a.score_breakdown or {}).get("badge", "testing"),
            "image": image_data_uri(a.screenshot_path) or image_data_uri(a.thumbnail_path),
            "library_url": f"https://www.facebook.com/ads/library/?id={a.library_id}",
        }
        for a in ads[:top_n]
    ]
    return {
        "brand": get_settings().get("reports", {}),
        "scan": scan,
        "competitor": competitor,
        "ads": ads,
        "top": top,
        "kpis": {
            "total": len(ads),
            "winners": badges.get("winner", 0),
            "promising": badges.get("promising", 0),
            "testing": badges.get("testing", 0),
            "avg_days": avg_days,
            "longest": max((a.days_running for a in ads), default=0),
        },
        "formats": formats.most_common(),
        "platforms": platforms.most_common(),
        "generated_at": datetime.now().strftime("%d %b %Y, %H:%M"),
        "sections": sections or DEFAULT_SECTIONS,
        "title": title or (competitor.name if competitor else f"Scan {scan_id}"),
    }


def build_scan_report(
    scan_id: int, out_path: Path | None = None, options: dict[str, Any] | None = None
) -> Path:
    options = options or {}
    ctx = scan_report_context(
        scan_id,
        top_n=int(options.get("top_n", 30)),
        sections=options.get("sections"),
        title=options.get("title"),
    )
    html = jinja_env().get_template("scan_report.html.j2").render(**ctx)
    if out_path is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        out_path = reports_dir() / f"{slugify(ctx['competitor'].name)}-scan{scan_id}-{stamp}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
