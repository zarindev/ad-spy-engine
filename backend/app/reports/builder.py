"""Branded competitor report: cover, executive summary, top winners, charts, change log, opportunities.

One builder serves every scope: a single scan, one competitor, a 2–3 brand comparison or every
competitor in a client folder. The HTML is self-contained (images embedded) and print-ready for
Chrome's PDF engine (A4, page numbers via CSS @page margin boxes).
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlmodel import select

from app.analysis import ai
from app.analysis.insights import (
    ads_for,
    brand_summary,
    change_log,
    highlights,
    opportunities_from_data,
    pct,
)
from app.analysis.scoring import BADGES, badge_range
from app.core.config import get_settings
from app.core.paths import TEMPLATES_DIR, data_dir, reports_dir, slugify
from app.db.models import Ad, AdAnalysis, Competitor, Scan
from app.db.session import session_scope

log = logging.getLogger(__name__)

SECTIONS = ["cover", "summary", "winners", "charts", "changes", "opportunities", "appendix"]
DEFAULT_SECTIONS = ["cover", "summary", "winners", "charts", "changes", "opportunities"]
LEGACY_SECTIONS = {"top_ads": "winners", "all_ads": "appendix"}
APPENDIX_LIMIT = 300


@dataclass
class ReportSpec:
    competitor_ids: list[int]
    scan_id: int | None = None
    title: str | None = None
    client_name: str | None = None
    sections: list[str] = field(default_factory=lambda: list(DEFAULT_SECTIONS))
    top_n: int = 10
    use_ai: bool = False
    days: int = 30
    own_only: bool = True


def normalize_sections(sections: list[str] | None) -> list[str]:
    wanted = {LEGACY_SECTIONS.get(s, s) for s in (sections or DEFAULT_SECTIONS)}
    return [s for s in SECTIONS if s in wanted]


# ----------------------------------------------------------------------------- helpers
def jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["thousands"] = lambda n: f"{n:,}" if isinstance(n, int) else n
    env.filters["label"] = lambda s: str(s or "").replace("_", " ").capitalize()
    return env


def image_data_uri(relative: str | None) -> str | None:
    """Embed local images so the report is a single portable file."""
    if not relative or relative.startswith("http"):
        return None
    path = data_dir() / relative
    if not path.is_file():
        return None
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    if not mime.startswith("image/"):
        return None
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def css_string(text: str) -> str:
    """Safe content for a CSS string (used in @page footers)."""
    return re.sub(r'["\\\n\r]', "", text)[:110]


def columns_svg(values: list[int], peak: int, color: str, width: int = 300, height: int = 56) -> str:
    """Tiny column chart (weekly launches) as inline SVG, on a shared y-scale."""
    if not values:
        return ""
    gap = 2
    bar_w = (width - gap * (len(values) - 1)) / len(values)
    bars = []
    for i, v in enumerate(values):
        h = 0 if not peak else max(round(v / peak * (height - 4), 1), 1.5 if v else 0)
        x = round(i * (bar_w + gap), 1)
        bars.append(
            f'<rect x="{x}" y="{height - h}" width="{round(bar_w, 1)}" height="{h}" rx="2" fill="{color}">'
            f"<title>{v} launched</title></rect>"
        )
    base = f'<line x1="0" x2="{width}" y1="{height}" y2="{height}" stroke="#D9D9E3" stroke-width="1"/>'
    return (
        f'<svg viewBox="0 0 {width} {height + 1}" width="100%" height="{height + 1}" '
        f'preserveAspectRatio="none" role="img">{"".join(bars)}{base}</svg>'
    )


def _hex(value: str | None, default: str) -> str:
    return value if value and re.fullmatch(r"#[0-9a-fA-F]{6}", value) else default


def branding() -> dict[str, Any]:
    cfg = get_settings().get("reports", {})
    return {
        "agency_name": (cfg.get("agency_name") or "Ad Spy Engine").strip(),
        "primary": _hex(cfg.get("primary_color"), "#6D28D9"),
        "accent": _hex(cfg.get("accent_color"), "#F59E0B"),
        "logo": image_data_uri(cfg.get("logo_path")),
    }


def _winner_item(ad: Ad, brand: str, analysis: AdAnalysis | None) -> dict[str, Any]:
    key = (ad.score_breakdown or {}).get("badge", "testing")
    return {
        "ad": ad,
        "brand": brand,
        "badge": BADGES[key],
        "badge_key": key,
        "image": image_data_uri(ad.thumbnail_path) or image_data_uri(ad.screenshot_path),
        "library_url": f"https://www.facebook.com/ads/library/?id={ad.library_id}",
        "why": (ad.score_breakdown or {}).get("explanation", [])[:2],
        "analysis": analysis,
    }


def _summary_points(brands: list[dict[str, Any]], all_ads: list[Ad]) -> list[str]:
    """Executive-summary bullets: measured facts only."""
    n = len(all_ads)
    if not n:
        return []
    win_lo = badge_range("winner")[0]
    winners = [a for a in all_ads if a.score >= win_lo]
    names = [b["name"] for b in brands]
    who = names[0] if len(names) == 1 else f"{len(names)} competitors ({', '.join(names)})"
    points = [
        f"We reviewed {n:,} ads from {who} in the public Meta Ad Library. "
        f"{len(winners)} ({pct(len(winners), n):g}%) score as Winners: ads kept live long enough, "
        "and varied enough, to suggest they are paying back."
    ]
    if winners:
        fmt = max({a.media_type for a in winners}, key=lambda f: sum(1 for a in winners if a.media_type == f))
        share = pct(sum(1 for a in winners if a.media_type == fmt), len(winners))
        points.append(f"{fmt.capitalize()} is the dominant winning format: {share:g}% of Winners.")
    longest = max(all_ads, key=lambda a: a.days_running)
    if longest.days_running:
        points.append(
            f"The longest-running ad ({longest.page_name}) has been live for {longest.days_running} days, "
            f"since {longest.start_date:%d %b %Y}."
            if longest.start_date
            else ""
        )
    recent = sum(b["stats"]["launched_30d"] for b in brands)
    points.append(f"{recent} of these ads were launched in the last 30 days.")
    points.extend(highlights(brands))
    return [p for p in points if p]


def _ai_payload(brands: list[dict[str, Any]], winners: list[dict[str, Any]], client: str | None) -> dict:
    keep = ("stats", "formats", "winner_formats", "placements", "ctas", "winner_ctas", "longevity")
    return {
        "client": client,
        "brands": [
            {
                "name": b["name"],
                **{k: b[k] for k in keep},
                "ai_insights": {
                    k: v
                    for k, v in b["insights"].items()
                    if k in ("analyzed", "hook_distribution", "top_angles")
                },
            }
            for b in brands
        ],
        "top_ads": [
            {
                "library_id": w["ad"].library_id,
                "brand": w["brand"],
                "score": w["ad"].score,
                "format": w["ad"].media_type,
                "days_running": w["ad"].days_running,
                "variations": w["ad"].variation_count,
                "headline": w["ad"].headline,
                "copy": (w["ad"].ad_copy or "")[:400],
                "cta": w["ad"].cta_text,
                "hook_type": w["analysis"].hook_type if w["analysis"] else None,
                "angle": w["analysis"].angle if w["analysis"] else None,
            }
            for w in winners
        ],
    }


# ----------------------------------------------------------------------------- context
def report_context(spec: ReportSpec, ai_client: Any | None = None) -> dict[str, Any]:
    sections = normalize_sections(spec.sections)
    with session_scope() as session:
        scan = session.get(Scan, spec.scan_id) if spec.scan_id else None
        if spec.scan_id and scan is None:
            raise ValueError(f"Scan {spec.scan_id} not found")
        ids = [scan.competitor_id] if scan else spec.competitor_ids
        comps = [c for cid in ids if (c := session.get(Competitor, cid))]
        if not comps:
            raise ValueError("No competitors in this report scope")

        brands = []
        for c in comps:
            ads, excluded = ads_for(session, c, spec.scan_id, own_only=spec.own_only)
            brands.append(brand_summary(session, c, ads, excluded=excluded))
        all_ads = sorted((a for b in brands for a in b["_ads"]), key=lambda a: (-a.score, -a.days_running))
        brand_of = {c.id: c.name for c in comps}
        pool = all_ads[: max(spec.top_n, 15)]
        analyses = {
            a.ad_id: a
            for a in session.exec(
                select(AdAnalysis).where(AdAnalysis.ad_id.in_([x.id for x in pool]))  # type: ignore[union-attr]
            ).all()
        }
        winners = [_winner_item(a, brand_of.get(a.competitor_id, ""), analyses.get(a.id)) for a in pool]
        changes = change_log(session, [c.id for c in comps], spec.days) if "changes" in sections else None  # type: ignore[misc]

    win_lo = badge_range("winner")[0]
    total = len(all_ads)
    winner_ads = [a for a in all_ads if a.score >= win_lo]
    brand = branding()
    for b in brands:
        b["logo_uri"] = image_data_uri(b["logo"])
        weekly = [w["launched"] for w in b["cadence"]]
        b["cadence_svg"] = columns_svg(weekly, max(weekly, default=0), brand["primary"])

    def share_list(values: list[str], whole: int, top: int | None = None) -> list[dict[str, Any]]:
        from collections import Counter

        return [{"name": k, "count": v, "share": pct(v, whole)} for k, v in Counter(values).most_common(top)]

    analyzed = sum(b["insights"].get("analyzed", 0) for b in brands)
    hooks: dict[str, int] = {}
    angles: dict[str, int] = {}
    for b in brands:
        for h in b["insights"].get("hook_distribution", []):
            hooks[h["name"]] = hooks.get(h["name"], 0) + h["count"]
        for a in b["insights"].get("top_angles", []):
            angles[a["name"]] = angles.get(a["name"], 0) + a["count"]

    ai_brief = None
    ai_meta: dict[str, Any] = {}
    if spec.use_ai and ("opportunities" in sections or "summary" in sections):
        try:
            ai_brief, ai_meta = ai.strategy_brief(
                _ai_payload(brands, winners[:15], spec.client_name), client=ai_client
            )
        except Exception as exc:  # noqa: BLE001 — the report still ships with data-derived content
            log.warning("AI opportunities failed: %s", exc)
            ai_meta = {"error": f"{type(exc).__name__}: {exc}"[:300]}

    by_library = {w["ad"].library_id: w for w in winners}
    ad_by_library = {a.library_id: a for a in all_ads}

    def evidence(ids: list[str]) -> list[dict[str, Any]]:
        out = []
        for lib in ids:
            if lib in by_library:
                out.append(by_library[lib])
            elif ad := ad_by_library.get(lib):
                out.append(_winner_item(ad, brand_of.get(ad.competitor_id, ""), None))
        return out[:3]

    opportunities: list[dict[str, Any]]
    if ai_brief is not None:
        opportunities = [
            {
                "title": o.title,
                "detail": o.why,
                "action": o.how_to_apply,
                "evidence_ads": evidence(o.evidence_library_ids),
            }
            for o in ai_brief.opportunities
        ]
    else:
        opportunities = [
            {**o, "evidence_ads": evidence([o["library_id"]] if o.get("library_id") else [])}
            for o in opportunities_from_data(brands)
        ]

    dates = [a.first_seen_at for a in all_ads if a.first_seen_at]
    names = [b["name"] for b in brands]
    default_title = names[0] if len(names) == 1 else " vs ".join(names)
    title = spec.title or default_title
    generated = datetime.now()
    return {
        "brand": brand,
        "title": title,
        "client_name": spec.client_name,
        "scan": scan,
        "brands": brands,
        "multi": len(brands) > 1,
        "sections": sections,
        "kpis": {
            "total": total,
            "brands": len(brands),
            "winners": len(winner_ads),
            "winner_rate": pct(len(winner_ads), total),
            "active": sum(1 for a in all_ads if a.status == "active"),
            "median_days": sorted(a.days_running for a in all_ads)[total // 2] if total else 0,
            "launched_30d": sum(b["stats"]["launched_30d"] for b in brands),
            "excluded": sum(b["stats"]["other_advertisers_excluded"] for b in brands),
        },
        "summary_points": _summary_points(brands, all_ads),
        "ai_summary": ai_brief.executive_summary if ai_brief else None,
        "ai_meta": ai_meta,
        "winners": winners[: spec.top_n],
        "charts": {
            "formats_all": share_list([a.media_type for a in all_ads], total),
            "formats_winners": share_list([a.media_type for a in winner_ads], len(winner_ads)),
            "placements": share_list([p for a in all_ads for p in a.platforms or []], total),
            "ctas": share_list([a.cta_text for a in all_ads if a.cta_text], total, top=6),
            "longevity": [
                {
                    "name": lb["name"],
                    "count": sum(
                        b2["count"] for b in brands for b2 in b["longevity"] if b2["name"] == lb["name"]
                    ),
                }
                for lb in brands[0]["longevity"]
            ],
            "hooks": sorted(hooks.items(), key=lambda kv: -kv[1]),
            "angles": sorted(angles.items(), key=lambda kv: -kv[1])[:8],
            "analyzed": analyzed,
        },
        "changes": changes,
        "opportunities": opportunities,
        "opportunities_source": "ai" if ai_brief else "data",
        "appendix": all_ads[:APPENDIX_LIMIT],
        "appendix_total": total,
        "collected_from": min(dates).strftime("%d %b %Y") if dates else None,
        "collected_to": max(dates).strftime("%d %b %Y") if dates else None,
        "generated_at": generated.strftime("%d %B %Y"),
        "footer": css_string(f"{brand['agency_name']} · {title}"),
    }


def render_report(
    spec: ReportSpec, out_path: Path | None = None, ai_client: Any | None = None
) -> tuple[Path, dict[str, Any]]:
    """Write the HTML report. Returns (path, meta) where meta carries AI usage or errors."""
    ctx = report_context(spec, ai_client=ai_client)
    html = jinja_env().get_template("brand_report.html.j2").render(**ctx)
    if out_path is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_path = reports_dir() / f"{slugify(ctx['title'])[:60] or 'report'}-{stamp}.html"
    out_path.write_text(html, encoding="utf-8")
    meta = {
        "ai_usage": ctx["ai_meta"],
        "opportunities_source": ctx["opportunities_source"],
        "ads": ctx["kpis"]["total"],
    }
    return out_path, meta


def build_scan_report(
    scan_id: int, out_path: Path | None = None, options: dict[str, Any] | None = None
) -> Path:
    """Report for one scan (CLI + legacy callers)."""
    options = options or {}
    spec = ReportSpec(
        competitor_ids=[],
        scan_id=scan_id,
        title=options.get("title"),
        sections=normalize_sections(options.get("sections") or DEFAULT_SECTIONS + ["appendix"]),
        top_n=int(options.get("top_n", 10)),
    )
    path, _ = render_report(spec, out_path)
    return path
