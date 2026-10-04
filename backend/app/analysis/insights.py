"""Brand-level analytics shared by the Compare screen and branded reports.

Everything here is computed from ads actually collected from the Ad Library. "Highlights" and
data-derived "opportunities" are templated sentences over those numbers, each carrying the
evidence it was built from, so nothing in a report is invented.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any

from sqlmodel import Session, select

from app.analysis.ai import competitor_insights
from app.analysis.scoring import badge_range
from app.db.models import Ad, AdSnapshot, ChangeEvent, Competitor, utcnow

LONGEVITY_BUCKETS = [
    ("≤ 7 days", 0, 7),
    ("8–30 days", 8, 30),
    ("31–90 days", 31, 90),
    ("90+ days", 91, 10**6),
]
CORE_FORMATS = ("image", "video", "carousel")
MIN_SAMPLE = 5  # never draw a conclusion from fewer ads than this


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def pct(part: float, whole: float) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def _norm(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def is_own_ad(ad: Ad, comp: Competitor) -> bool:
    """Keyword scans also return other advertisers that mention the brand; keep the brand's own pages."""
    if comp.page_id and ad.page_id == comp.page_id:
        return True
    name = _norm(comp.name)
    return bool(name) and name in _norm(ad.page_name)


def ads_for(
    session: Session, comp: Competitor, scan_id: int | None = None, own_only: bool = True
) -> tuple[list[Ad], int]:
    """A brand's ads, best first. Returns (ads, n excluded as other advertisers).

    With own_only, ads from other pages are dropped unless none of the ads match the brand (then the
    filter can't tell who the brand is and everything is kept).
    """
    stmt = select(Ad).where(Ad.competitor_id == comp.id)
    if scan_id is not None:
        stmt = select(Ad).join(AdSnapshot, AdSnapshot.ad_id == Ad.id).where(AdSnapshot.scan_id == scan_id)
    ads = list(session.exec(stmt.order_by(Ad.score.desc(), Ad.days_running.desc())).all())  # type: ignore[attr-defined]
    if not own_only:
        return ads, 0
    own = [a for a in ads if is_own_ad(a, comp)]
    if not own:
        return ads, 0
    return own, len(ads) - len(own)


def counts(values: list[str], total: int, top: int | None = None) -> list[dict[str, Any]]:
    return [{"name": k, "count": v, "share": pct(v, total)} for k, v in Counter(values).most_common(top)]


def brand_summary(
    session: Session, comp: Competitor, ads: list[Ad], weeks: int = 12, excluded: int = 0
) -> dict[str, Any]:
    """Side-by-side numbers for one brand. `excluded` = ads dropped as other advertisers."""
    n = len(ads)
    win_lo = badge_range("winner")[0]
    prom_lo = badge_range("promising")[0]
    winners = [a for a in ads if a.score >= win_lo]
    days = [a.days_running for a in ads]
    today = utcnow().date()

    first_week = week_start(today - timedelta(weeks=weeks - 1))
    launches = Counter(week_start(a.start_date) for a in ads if a.start_date and a.start_date >= first_week)
    cadence = []
    week = first_week
    while week <= today:
        cadence.append({"week": week.isoformat(), "launched": launches.get(week, 0)})
        week += timedelta(weeks=1)

    groups: dict[str, list[Ad]] = defaultdict(list)
    for a in ads:
        if a.group_key and a.group_size > 1:
            groups[a.group_key].append(a)
    biggest = max(groups.values(), key=len, default=[])

    by_format: dict[str, list[Ad]] = defaultdict(list)
    for a in ads:
        by_format[a.media_type].append(a)

    return {
        "id": comp.id,
        "name": comp.name,
        "logo": comp.logo_url,
        "client_id": comp.client_id,
        "last_scan_at": comp.last_scan_at.isoformat() if comp.last_scan_at else None,
        "stats": {
            "ads": n,
            "active": sum(1 for a in ads if a.status == "active"),
            "winners": len(winners),
            "promising": sum(1 for a in ads if prom_lo <= a.score < win_lo),
            "winner_rate": pct(len(winners), n),
            "avg_score": round(sum(a.score for a in ads) / n, 1) if n else 0,
            "avg_days": round(sum(days) / n, 1) if n else 0,
            "median_days": statistics.median(days) if days else 0,
            "max_days": max(days, default=0),
            "launched_30d": sum(
                1 for a in ads if a.start_date and a.start_date >= today - timedelta(days=30)
            ),
            "variation_groups": len(groups),
            "largest_group": len(biggest),
            "other_advertisers_excluded": excluded,
        },
        "formats": counts([a.media_type for a in ads], n),
        "winner_formats": counts([a.media_type for a in winners], len(winners)),
        "format_winner_rate": {
            fmt: {
                "ads": len(items),
                "winner_rate": pct(sum(1 for a in items if a.score >= win_lo), len(items)),
            }
            for fmt, items in by_format.items()
        },
        "placements": counts([p for a in ads for p in a.platforms or []], n),
        "ctas": counts([a.cta_text for a in ads if a.cta_text], n, top=6),
        "winner_ctas": counts([a.cta_text for a in winners if a.cta_text], len(winners), top=4),
        "longevity": [
            {"name": label, "count": (c := sum(1 for d in days if lo <= d <= hi)), "share": pct(c, n)}
            for label, lo, hi in LONGEVITY_BUCKETS
        ],
        "cadence": cadence,
        "insights": competitor_insights(session, comp.id),  # type: ignore[arg-type]
        "_ads": ads,
        "_biggest_group": biggest,
    }


def _leader(brands: list[dict[str, Any]], key: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    ranked = sorted(brands, key=lambda b: b["stats"][key], reverse=True)
    if len(ranked) < 2 or ranked[0]["stats"][key] == ranked[-1]["stats"][key]:
        return None
    return ranked[0], ranked[-1]


def _share(brand: dict[str, Any], fmt: str) -> float:
    return next((f["share"] for f in brand["formats"] if f["name"] == fmt), 0.0)


def highlights(brands: list[dict[str, Any]]) -> list[str]:
    """Plain-language comparisons between 2+ brands, each a statement of measured numbers."""
    brands = [b for b in brands if b["stats"]["ads"] >= MIN_SAMPLE]
    out: list[str] = []
    if len(brands) < 2:
        return out
    if lead := _leader(brands, "winner_rate"):
        hi, lo = lead
        out.append(
            f"{hi['name']} has the highest share of Winner ads ({hi['stats']['winner_rate']:g}% vs "
            f"{lo['stats']['winner_rate']:g}% for {lo['name']})."
        )
    if lead := _leader(brands, "median_days"):
        hi, lo = lead
        out.append(
            f"{hi['name']}'s ads run longest: median {hi['stats']['median_days']:g} days vs "
            f"{lo['stats']['median_days']:g} for {lo['name']}."
        )
    if lead := _leader(brands, "launched_30d"):
        hi, lo = lead
        out.append(
            f"{hi['name']} launched the most new ads in the last 30 days ({hi['stats']['launched_30d']} vs "
            f"{lo['stats']['launched_30d']} for {lo['name']})."
        )
    video = sorted(brands, key=lambda b: _share(b, "video"), reverse=True)
    if _share(video[0], "video") - _share(video[-1], "video") >= 15:
        out.append(
            f"{video[0]['name']} leans on video ({_share(video[0], 'video'):g}% of ads) while "
            f"{video[-1]['name']} uses it for {_share(video[-1], 'video'):g}%."
        )
    if lead := _leader(brands, "largest_group"):
        hi, _ = lead
        if hi["stats"]["largest_group"] >= 3:
            out.append(
                f"{hi['name']} is iterating hardest on a single concept: {hi['stats']['largest_group']} "
                "ads share one creative or near-identical copy."
            )
    return out


def opportunities_from_data(brands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rule-based opportunities: patterns in competitors' winners worth adopting and lanes nobody uses.

    Each item has a title, an explanation and the evidence numbers it rests on.
    """
    all_ads: list[Ad] = [a for b in brands for a in b["_ads"]]
    total = len(all_ads)
    if total < MIN_SAMPLE:
        return []
    win_lo = badge_range("winner")[0]
    winners = [a for a in all_ads if a.score >= win_lo]
    overall_rate = pct(len(winners), total)
    names = ", ".join(b["name"] for b in brands)
    out: list[dict[str, Any]] = []

    # 1) The format that most often becomes a Winner.
    by_format: dict[str, list[Ad]] = defaultdict(list)
    for a in all_ads:
        by_format[a.media_type].append(a)
    rates = {
        fmt: pct(sum(1 for a in items if a.score >= win_lo), len(items))
        for fmt, items in by_format.items()
        if len(items) >= MIN_SAMPLE
    }
    if len(rates) >= 2:
        best = max(rates, key=lambda f: rates[f])
        if rates[best] >= overall_rate + 5:
            out.append(
                {
                    "title": f"Lead with {best} creative",
                    "detail": f"{rates[best]:g}% of {best} ads reach Winner status, against {overall_rate:g}% "
                    f"across all formats, so these are the ads competitors keep running.",
                    "evidence": f"{len(by_format[best])} {best} ads across {names}",
                }
            )

    # 2) Formats almost nobody uses.
    for fmt in CORE_FORMATS:
        share = pct(len(by_format.get(fmt, [])), total)
        if share < 5:
            out.append(
                {
                    "title": f"Open lane: {fmt} ads",
                    "detail": f"Only {share:g}% of the {total} competitor ads collected are {fmt}s. A strong {fmt} "
                    "concept would stand out where this format is rare among these brands.",
                    "evidence": f"{len(by_format.get(fmt, []))} of {total} ads",
                }
            )

    # 3) The longest-running proof point.
    longest = max(all_ads, key=lambda a: a.days_running)
    if longest.days_running >= 60:
        label = (longest.headline or (longest.ad_copy or "")[:70] or "untitled").strip()
        out.append(
            {
                "title": "Study the longest-running ad",
                "detail": f"{longest.page_name} has kept “{label}” live for {longest.days_running} days. "
                "An ad usually stays live that long only when it is paying back. Break down its hook, "
                "offer and format.",
                "evidence": f"Library ID {longest.library_id}",
                "library_id": longest.library_id,
            }
        )

    # 4) A concept being scaled through many variations.
    biggest = max(brands, key=lambda b: len(b["_biggest_group"]))
    group = biggest["_biggest_group"]
    if len(group) >= 3:
        lead = max(group, key=lambda a: a.score)
        out.append(
            {
                "title": f"Borrow {biggest['name']}'s most-tested concept",
                "detail": f"{len(group)} {biggest['name']} ads share one creative or near-identical copy. "
                "Scaling one idea through many variations is a strong sign it works.",
                "evidence": f"Lead ad: Library ID {lead.library_id} (score {lead.score})",
                "library_id": lead.library_id,
            }
        )

    # 5) The call to action winners use.
    ctas = Counter(a.cta_text for a in winners if a.cta_text)
    if len(winners) >= MIN_SAMPLE and ctas:
        cta, n = ctas.most_common(1)[0]
        overall = pct(sum(1 for a in all_ads if a.cta_text == cta), total)
        winner_share = pct(n, len(winners))
        if winner_share >= overall + 5:
            out.append(
                {
                    "title": f"Test the “{cta}” button",
                    "detail": f"“{cta}” appears on {winner_share:g}% of Winner ads but only {overall:g}% of all "
                    "ads, so it is over-represented among the long-runners.",
                    "evidence": f"{n} of {len(winners)} Winners",
                }
            )

    # 6) Hook types nobody is using (needs AI analysis).
    hooks: Counter[str] = Counter()
    analyzed = 0
    for b in brands:
        analyzed += b["insights"].get("analyzed", 0)
        for h in b["insights"].get("hook_distribution", []):
            hooks[h["name"]] += h["count"]
    if analyzed >= 10:
        from app.analysis.ai import HOOK_TYPES

        rare = [h for h in HOOK_TYPES if pct(hooks.get(h, 0), analyzed) < 5]
        if rare:
            pretty = ", ".join(h.replace("_", " ") for h in rare[:3])
            out.append(
                {
                    "title": "Hooks competitors are not using",
                    "detail": f"Among {analyzed} AI-analyzed ads, these opening styles are rare: {pretty}. "
                    "Testing one gives you a pattern-interrupt in this category.",
                    "evidence": ", ".join(f"{h}: {hooks.get(h, 0)}" for h in rare[:3]),
                }
            )
    return out[:6]


def change_log(session: Session, competitor_ids: list[int], days: int = 30) -> dict[str, Any]:
    since = utcnow() - timedelta(days=days)
    rows = session.exec(
        select(ChangeEvent, Ad, Competitor)
        .join(Ad, Ad.id == ChangeEvent.ad_id)
        .join(Competitor, Competitor.id == ChangeEvent.competitor_id)
        .where(ChangeEvent.competitor_id.in_(competitor_ids), ChangeEvent.created_at >= since)  # type: ignore[attr-defined]
        .order_by(ChangeEvent.created_at.desc())  # type: ignore[attr-defined]
    ).all()
    per_brand: dict[str, Counter[str]] = defaultdict(Counter)
    for ev, _, comp in rows:
        per_brand[comp.name][ev.kind] += 1
    return {
        "days": days,
        "total": len(rows),
        "per_brand": [
            {"name": k, **{kind: v.get(kind, 0) for kind in ("new", "stopped", "scaled")}}
            for k, v in per_brand.items()
        ],
        "events": [
            {
                "date": ev.created_at.date(),
                "brand": comp.name,
                "kind": ev.kind,
                "details": ev.details or {},
                "ad": ad,
            }
            for ev, ad, comp in rows[:25]
        ],
    }


def public(summary: dict[str, Any]) -> dict[str, Any]:
    """Drop private (ORM) keys before returning JSON."""
    return {k: v for k, v in summary.items() if not k.startswith("_")}
