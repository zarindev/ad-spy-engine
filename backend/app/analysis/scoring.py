"""Winner Score (0–100): how likely an ad is a proven, scaled performer.

    longevity  = min(days_running / 90, 1.0)            weight 0.55
    variations = min(log2(variation_count + 1) / 4, 1)  weight 0.25
    platforms  = min(len(platforms) / 4, 1.0)           weight 0.10
    recency_ok = 1 if still active else 0               weight 0.10
    score      = round(100 * weighted_sum)

Weights and thresholds live in config/settings.yaml (`scoring`).
"""

from __future__ import annotations

import math
from typing import Any

from app.core.config import get_settings

BADGES = {
    "winner": {"label": "Winner", "emoji": "🏆"},
    "promising": {"label": "Promising", "emoji": "📈"},
    "testing": {"label": "Testing", "emoji": "🧪"},
}


def scoring_config() -> dict[str, Any]:
    return get_settings().get("scoring", {})


def compute_score(
    days_running: int,
    variation_count: int,
    platforms: list[str] | None,
    is_active: bool,
    config: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Return (score, breakdown). The breakdown powers the "Why this score" panel."""
    cfg = config or scoring_config()
    weights = cfg.get("weights", {})
    w_long = float(weights.get("longevity", 0.55))
    w_var = float(weights.get("variations", 0.25))
    w_plat = float(weights.get("platforms", 0.10))
    w_rec = float(weights.get("recency", 0.10))

    full_days = float(cfg.get("longevity_full_days", 90))
    log_cap = float(cfg.get("variations_log2_cap", 4))
    plat_total = float(cfg.get("platforms_total", 4))

    days = max(int(days_running or 0), 0)
    variations = max(int(variation_count or 1), 1)
    n_platforms = len(set(platforms or []))

    components = {
        "longevity": min(days / full_days, 1.0),
        "variations": min(math.log2(variations + 1) / log_cap, 1.0),
        "platforms": min(n_platforms / plat_total, 1.0) if plat_total else 0.0,
        "recency": 1.0 if is_active else 0.0,
    }
    weight_map = {"longevity": w_long, "variations": w_var, "platforms": w_plat, "recency": w_rec}
    weighted = {k: components[k] * weight_map[k] for k in components}
    score = int(round(100 * sum(weighted.values())))
    score = max(0, min(score, 100))

    breakdown = {
        "score": score,
        "badge": badge_for(score, cfg),
        "inputs": {
            "days_running": days,
            "variation_count": variations,
            "platform_count": n_platforms,
            "is_active": is_active,
        },
        "components": {
            k: {
                "value": round(components[k], 4),
                "weight": weight_map[k],
                "points": round(100 * weighted[k], 1),
                "max_points": round(100 * weight_map[k], 1),
            }
            for k in components
        },
        "explanation": explain(days, variations, n_platforms, is_active, full_days),
    }
    return score, breakdown


def badge_for(score: int, config: dict[str, Any] | None = None) -> str:
    thresholds = (config or scoring_config()).get("thresholds", {})
    if score >= int(thresholds.get("winner", 75)):
        return "winner"
    if score >= int(thresholds.get("promising", 50)):
        return "promising"
    return "testing"


def explain(days: int, variations: int, n_platforms: int, active: bool, full_days: float) -> list[str]:
    lines = []
    if days >= full_days:
        lines.append(f"Running {days} days — advertisers rarely keep paying for losers this long.")
    elif days >= 30:
        lines.append(f"Running {days} days — survived the typical 2–4 week testing window.")
    else:
        lines.append(f"Only {days} days old — still likely in testing.")
    if variations >= 4:
        lines.append(f"{variations} variations — the creative is being scaled or iterated.")
    elif variations > 1:
        lines.append(f"{variations} variations — some copy/creative testing.")
    else:
        lines.append("Single version — no visible iteration yet.")
    lines.append(f"Delivered on {n_platforms} placement{'s' if n_platforms != 1 else ''}.")
    lines.append("Still active." if active else "No longer running.")
    return lines


def badge_range(badge: str, config: dict[str, Any] | None = None) -> tuple[int, int]:
    """Inclusive score range for a badge — used for DB filtering."""
    thresholds = (config or scoring_config()).get("thresholds", {})
    winner, promising = int(thresholds.get("winner", 75)), int(thresholds.get("promising", 50))
    return {"winner": (winner, 100), "promising": (promising, winner - 1), "testing": (0, promising - 1)}[
        badge
    ]
