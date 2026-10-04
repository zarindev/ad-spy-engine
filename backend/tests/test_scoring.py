from __future__ import annotations

import pytest

from app.analysis.scoring import badge_for, compute_score

CFG = {
    "weights": {"longevity": 0.55, "variations": 0.25, "platforms": 0.10, "recency": 0.10},
    "longevity_full_days": 90,
    "variations_log2_cap": 4,
    "platforms_total": 4,
    "thresholds": {"winner": 75, "promising": 50},
}


def test_maximum_score():
    score, breakdown = compute_score(
        120, 15, ["FACEBOOK", "INSTAGRAM", "MESSENGER", "AUDIENCE_NETWORK"], True, CFG
    )
    assert score == 100
    assert breakdown["badge"] == "winner"


def test_minimum_score():
    score, _ = compute_score(0, 1, [], False, CFG)
    # only variations contributes: log2(2)/4 * 0.25 = 0.0625
    assert score == 6


def test_spec_formula_example():
    # 45 days, 3 variations, 2 platforms, active:
    # 0.55*0.5 + 0.25*min(log2(4)/4,1)=0.125 + 0.10*0.5 + 0.10 = 0.55
    score, breakdown = compute_score(45, 3, ["FACEBOOK", "INSTAGRAM"], True, CFG)
    assert score == 55
    assert breakdown["badge"] == "promising"
    assert breakdown["components"]["longevity"]["points"] == 27.5
    assert sum(c["points"] for c in breakdown["components"].values()) == pytest.approx(55, abs=0.1)


def test_more_than_four_platforms_is_capped():
    six = ["FACEBOOK", "INSTAGRAM", "MESSENGER", "AUDIENCE_NETWORK", "THREADS", "WHATSAPP"]
    score_six, b = compute_score(10, 1, six, True, CFG)
    score_four, _ = compute_score(10, 1, six[:4], True, CFG)
    assert score_six == score_four
    assert b["components"]["platforms"]["value"] == 1.0


@pytest.mark.parametrize(
    "score,badge",
    [(100, "winner"), (75, "winner"), (74, "promising"), (50, "promising"), (49, "testing"), (0, "testing")],
)
def test_badges(score, badge):
    assert badge_for(score, CFG) == badge


def test_breakdown_has_explanation():
    _, breakdown = compute_score(100, 5, ["FACEBOOK"], True, CFG)
    assert any("100 days" in line for line in breakdown["explanation"])
    assert breakdown["inputs"]["variation_count"] == 5
