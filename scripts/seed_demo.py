"""Build the demo dataset in data-demo/ (fictional brands, generated creatives).

    python scripts/seed_demo.py            # (re)create data-demo/
    python scripts/seed_demo.py --no-pdf   # skip the sample PDF reports (no Chrome needed)
    python backend/run.py --demo           # browse it

Every brand, ad, creative and AI note here is invented, so screenshots and demos never show a
real company's ads. The dataset is only used with `--demo`, which also switches live scans, AI
runs and schedules off. Scan timings reuse the ads-per-minute measured in docs/benchmarks.json
(real scans) when that file exists.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import shutil
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "data-demo"
sys.path.insert(0, str(ROOT / "backend"))

from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

TODAY = date.today()
RNG = random.Random(20261004)
PLATFORMS = ["FACEBOOK", "INSTAGRAM", "MESSENGER", "AUDIENCE_NETWORK", "THREADS"]
SCAN_DAYS_AGO = [14, 7, 0]  # three scans per brand → real change events between them


# ----------------------------------------------------------------------------- brands
@dataclass
class Concept:
    hook_type: str
    headline: str
    hook: str
    body: str
    angle: str
    emotion: str
    offer: str | None
    cta: str
    media: str  # image | video | carousel | dynamic
    layout: str  # hero | split | quote | offer | grid
    age: tuple[int, int]  # days since launch range for the lead ad
    variants: int = 1
    ended_days_ago: int | None = None  # stopped running this many days ago
    scaled: bool = False  # gained variations between the last two scans
    steal: str = ""


@dataclass
class Brand:
    name: str
    domain: str
    palette: tuple[str, str, str]  # background, accent, ink
    product: str  # bottle | jar | mountain | cup
    tagline: str
    concepts: list[Concept] = field(default_factory=list)


BRANDS: list[Brand] = [
    Brand(
        "Lumen Skincare",
        "lumenskincare.example",
        ("#F6E3D9", "#E07A5F", "#3D2A22"),
        "bottle",
        "Vitamin C serum, made for sensitive skin",
        [
            Concept(
                "bold_claim",
                "Glow in 14 days, or it's free",
                "Visible glow in 14 days, or your money back.",
                "Our 15% vitamin C serum is buffered for sensitive skin, so you get the brightness without the sting.",
                "risk-free results guarantee",
                "confidence",
                "Money-back guarantee",
                "Shop now",
                "image",
                "hero",
                (150, 190),
                6,
                steal="Lead with a time-boxed result and pair it with a guarantee that removes the risk.",
            ),
            Concept(
                "social_proof",
                "38,000 five-star reviews",
                "38,000 people switched their serum last year. Here's why.",
                "Dermatologist-tested, fragrance-free and gentle enough for daily use.",
                "crowd validation",
                "trust",
                None,
                "Shop now",
                "video",
                "quote",
                (120, 140),
                5,
                scaled=True,
                steal="Open with a specific review count instead of a vague 'loved by thousands'.",
            ),
            Concept(
                "problem_agitate",
                "Dull skin by 3pm?",
                "Foundation looking flat by 3pm?",
                "Dehydrated skin scatters light. Two drops in the morning keep it plump all day.",
                "fixing afternoon dullness",
                "frustration",
                None,
                "Learn more",
                "video",
                "split",
                (95, 110),
                4,
                steal="Name the exact moment the problem shows up so the viewer recognises themselves.",
            ),
            Concept(
                "offer",
                "Your first bottle: 30% off",
                "New here? Your first bottle is 30% off.",
                "Free shipping, free returns, and a routine guide in every box.",
                "first-order discount",
                "excitement",
                "30% off first order",
                "Shop now",
                "carousel",
                "offer",
                (60, 75),
                3,
                steal="Bundle a how-to guide with the discount so the offer feels like more than a price cut.",
            ),
            Concept(
                "story",
                "I stopped wearing foundation",
                '"I stopped wearing foundation in March." (Maya, 34)',
                "Maya swapped three products for one serum. Her 8-week routine, step by step.",
                "simplified routine",
                "relief",
                None,
                "Learn more",
                "video",
                "quote",
                (40, 55),
                4,
                steal="Use a first-person transformation headline in quotes; it reads like UGC, not an ad.",
            ),
            Concept(
                "curiosity",
                "The serum mistake 9 in 10 make",
                "9 in 10 people apply vitamin C at the wrong time.",
                "It's not the formula. It's the order. Here's the 3-step routine that fixes it.",
                "routine education",
                "curiosity",
                None,
                "Learn more",
                "image",
                "hero",
                (20, 30),
                3,
                steal="Turn a usage mistake into the hook; education ads keep running when they sell the routine.",
            ),
            Concept(
                "question",
                "Sensitive skin + vitamin C?",
                "Think vitamin C is too harsh for you?",
                "Our buffered formula was tested on 120 people with reactive skin. 94% saw no irritation.",
                "safe for sensitive skin",
                "reassurance",
                None,
                "Shop now",
                "image",
                "split",
                (8, 14),
                2,
            ),
            Concept(
                "offer",
                "Holiday duo: serum + SPF",
                "The duo our customers buy together, now bundled.",
                "Serum in the morning, SPF on top. Save 20% when you get both.",
                "bundle value",
                "anticipation",
                "20% off the duo",
                "Shop now",
                "dynamic",
                "grid",
                (2, 6),
                3,
            ),
            Concept(
                "bold_claim",
                "Clinically shown: +31% radiance",
                "+31% radiance in a 4-week clinical study.",
                "Independent lab, 60 participants, measured with a chromameter.",
                "clinical proof",
                "trust",
                None,
                "Learn more",
                "image",
                "hero",
                (25, 35),
                1,
                ended_days_ago=10,
            ),
            Concept(
                "social_proof",
                "Editors' pick",
                "The serum beauty editors keep reordering.",
                "Featured in 12 roundups this year.",
                "authority",
                "trust",
                None,
                "Shop now",
                "image",
                "quote",
                (30, 40),
                2,
                ended_days_ago=4,
            ),
        ],
    ),
    Brand(
        "Dewdrop Labs",
        "dewdroplabs.example",
        ("#DDF3EE", "#3BA99C", "#10393A"),
        "jar",
        "Barrier-repair moisturiser",
        [
            Concept(
                "problem_agitate",
                "Tight, flaky skin after washing?",
                "Skin feels tight 10 minutes after cleansing?",
                "That's a damaged barrier. Ceramides + squalane rebuild it overnight.",
                "barrier repair",
                "frustration",
                None,
                "Shop now",
                "image",
                "split",
                (110, 130),
                4,
                steal="Describe the physical sensation of the problem, then name the cause.",
            ),
            Concept(
                "offer",
                "Free travel size with every jar",
                "Free travel size with every jar this week.",
                "Keep one at home, one in your bag.",
                "gift with purchase",
                "excitement",
                "Free travel size",
                "Shop now",
                "carousel",
                "offer",
                (20, 28),
                3,
            ),
            Concept(
                "social_proof",
                "Rated 4.8 by 9,000 customers",
                "Rated 4.8/5 by 9,000 customers with dry skin.",
                "Fragrance-free, non-comedogenic, vegan.",
                "crowd validation",
                "trust",
                None,
                "Shop now",
                "image",
                "quote",
                (70, 80),
                2,
            ),
            Concept(
                "curiosity",
                "Why your moisturiser stops working",
                "Your moisturiser didn't stop working. Your barrier did.",
                "A 60-second explainer from our chemist.",
                "skin science",
                "curiosity",
                None,
                "Learn more",
                "video",
                "hero",
                (12, 18),
                2,
            ),
            Concept(
                "story",
                "Winter skin diary",
                "Day 1 vs day 21 of the winter skin reset.",
                "Real customer, no filters, same lighting.",
                "visible transformation",
                "hope",
                None,
                "Learn more",
                "video",
                "split",
                (3, 7),
                2,
            ),
        ],
    ),
    Brand(
        "Northpeak Outdoor",
        "northpeak.example",
        ("#1E3A2F", "#E9C46A", "#F4F1E8"),
        "mountain",
        "Ultralight gear for long trails",
        [
            Concept(
                "bold_claim",
                "980 g. The whole shelter.",
                "Our two-person tent weighs 980 g. Packed.",
                "Single-wall, 15-denier silnylon, pitched with your trekking poles.",
                "ultralight performance",
                "ambition",
                None,
                "Shop now",
                "video",
                "hero",
                (180, 210),
                7,
                steal="Make one hard number the entire headline; specs sell when they're surprising.",
            ),
            Concept(
                "story",
                "2,650 miles on one pack",
                "Elena carried this pack 2,650 miles. It's still her daily bag.",
                "Watch the gear breakdown from her thru-hike.",
                "proven durability",
                "inspiration",
                None,
                "Learn more",
                "video",
                "split",
                (100, 120),
                5,
                scaled=True,
                steal="Borrow credibility from a real customer's journey and show the worn product.",
            ),
            Concept(
                "question",
                "How heavy is your base weight?",
                "Is your base weight still over 10 kg?",
                "Swap three items and drop 2.4 kg. Our checklist shows which.",
                "lighter pack",
                "aspiration",
                None,
                "Learn more",
                "carousel",
                "grid",
                (50, 60),
                3,
            ),
            Concept(
                "offer",
                "Trail season: free repairs for life",
                "Every Northpeak pack comes with free repairs for life.",
                "Rip it, send it, we fix it. No receipts needed.",
                "lifetime repair promise",
                "security",
                "Free lifetime repairs",
                "Shop now",
                "image",
                "offer",
                (85, 95),
                3,
                steal="Sell the guarantee, not the discount; it supports a premium price.",
            ),
            Concept(
                "social_proof",
                "Trusted by 400 trail crews",
                "Used by 400+ trail maintenance crews.",
                "Built for daily abuse, tested in the Cascades.",
                "professional endorsement",
                "trust",
                None,
                "Shop now",
                "image",
                "quote",
                (30, 40),
                2,
            ),
            Concept(
                "curiosity",
                "The 3 items we never pack",
                "Three things our guides never pack anymore.",
                "And what they carry instead.",
                "expert insider tips",
                "curiosity",
                None,
                "Learn more",
                "video",
                "hero",
                (5, 10),
                2,
            ),
            Concept(
                "offer",
                "Spring sale: 25% off shelters",
                "25% off every shelter until Sunday.",
                "Including the 980 g Ridgeline 2.",
                "seasonal sale",
                "urgency",
                "25% off shelters",
                "Shop now",
                "dynamic",
                "offer",
                (14, 20),
                3,
                ended_days_ago=3,
            ),
        ],
    ),
    Brand(
        "Brewlab Coffee",
        "brewlab.example",
        ("#2E1B12", "#D08C60", "#F6EBDD"),
        "cup",
        "Single-origin coffee, roasted to order",
        [
            Concept(
                "offer",
                "Your first bag is on us",
                "Your first bag of single-origin is on us.",
                "Pick a roast profile, we ship within 48 hours of roasting. Cancel anytime.",
                "free trial subscription",
                "curiosity",
                "First bag free",
                "Sign up",
                "image",
                "offer",
                (160, 175),
                6,
                steal="A free first unit plus 'cancel anytime' lowers the barrier for subscriptions.",
            ),
            Concept(
                "social_proof",
                "Rated the best home espresso beans",
                "Voted best home espresso beans by 2,300 baristas.",
                "Chocolate, cherry, a long caramel finish.",
                "expert validation",
                "trust",
                None,
                "Shop now",
                "video",
                "quote",
                (90, 105),
                4,
                steal="Quote the expert audience, not just customers; it upgrades the product's status.",
            ),
            Concept(
                "problem_agitate",
                "Bitter coffee isn't your fault",
                "Bitter coffee at home? It's probably stale beans.",
                "Supermarket coffee is roasted months ago. Ours ships within 48 hours.",
                "freshness",
                "frustration",
                None,
                "Learn more",
                "video",
                "split",
                (45, 55),
                4,
                scaled=True,
            ),
            Concept(
                "story",
                "From a 2-person roastery",
                "We started roasting in a garage with one 5 kg machine.",
                "Six years later, we still taste every batch.",
                "craft origin story",
                "warmth",
                None,
                "Learn more",
                "image",
                "hero",
                (25, 30),
                2,
            ),
            Concept(
                "question",
                "Which roast are you?",
                "Fruity, chocolatey or bold: which roast are you?",
                "Take the 30-second quiz and get a matched bag.",
                "personalisation",
                "playfulness",
                None,
                "Learn more",
                "carousel",
                "grid",
                (6, 12),
                3,
            ),
            Concept(
                "offer",
                "Gift subscriptions, 3 months",
                "Give 3 months of fresh coffee. Delivered monthly.",
                "Add a note and choose the start date.",
                "gifting",
                "generosity",
                "Gift subscription",
                "Shop now",
                "dynamic",
                "offer",
                (1, 4),
                2,
            ),
        ],
    ),
]

CLIENTS = [
    (
        "Solace Skin",
        "DTC skincare brand launching a vitamin C serum in Q1. Wants to see what Lumen and Dewdrop scale.",
        ["Lumen Skincare", "Dewdrop Labs"],
    ),
    (
        "Morning Ritual Co.",
        "Specialty coffee subscription. Focus: offer structure and retention angles.",
        ["Brewlab Coffee"],
    ),
]


# ----------------------------------------------------------------------------- drawing
def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        [
            "arialbd.ttf",
            "Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        if bold
        else [
            "arial.ttf",
            "Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    )
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def mix(a: str, b: str, t: float) -> tuple[int, int, int]:
    ra, rb = hex_rgb(a), hex_rgb(b)
    return tuple(int(x + (y - x) * t) for x, y in zip(ra, rb, strict=True))  # type: ignore[return-value]


def draw_product(
    img: Image.Image, kind: str, box: tuple[int, int, int, int], brand: Brand, seed: int
) -> None:
    bg, accent, ink = brand.palette
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    cx, w, h = (x0 + x1) // 2, x1 - x0, y1 - y0
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse(
        (cx - w * 0.32, y1 - h * 0.06, cx + w * 0.32, y1 + h * 0.04), fill=(0, 0, 0, 70)
    )
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(10)))
    if kind == "bottle":
        bw = w * 0.34
        d.rounded_rectangle((cx - bw / 2, y0 + h * 0.32, cx + bw / 2, y1), radius=int(bw * 0.28), fill=accent)
        d.rounded_rectangle(
            (cx - bw * 0.22, y0 + h * 0.14, cx + bw * 0.22, y0 + h * 0.34), radius=10, fill=ink
        )
        d.ellipse((cx - bw * 0.16, y0, cx + bw * 0.16, y0 + h * 0.18), fill=ink)
        d.rounded_rectangle(
            (cx - bw * 0.36, y0 + h * 0.55, cx + bw * 0.36, y0 + h * 0.78),
            radius=8,
            fill=mix(bg, "#FFFFFF", 0.6),
        )
        d.text((cx, y0 + h * 0.665), "LUMEN", font=font(int(bw * 0.17)), fill=ink, anchor="mm")
    elif kind == "jar":
        jw = w * 0.62
        d.rounded_rectangle(
            (cx - jw / 2, y0 + h * 0.38, cx + jw / 2, y1), radius=int(jw * 0.16), fill=mix(bg, "#FFFFFF", 0.7)
        )
        d.rounded_rectangle(
            (cx - jw * 0.53, y0 + h * 0.26, cx + jw * 0.53, y0 + h * 0.42), radius=14, fill=accent
        )
        d.text((cx, y0 + h * 0.7), "dewdrop", font=font(int(jw * 0.13)), fill=ink, anchor="mm")
    elif kind == "mountain":
        d.polygon(
            [
                (x0, y1),
                (x0 + w * 0.38, y0 + h * 0.15),
                (x0 + w * 0.62, y0 + h * 0.5),
                (x0 + w * 0.78, y0 + h * 0.32),
                (x1, y1),
            ],
            fill=mix(bg, ink, 0.18),
        )
        d.polygon(
            [(x0 + w * 0.3, y0 + h * 0.28), (x0 + w * 0.38, y0 + h * 0.15), (x0 + w * 0.46, y0 + h * 0.28)],
            fill=ink,
        )
        tw = w * 0.42
        d.polygon([(cx - tw / 2, y1 - 4), (cx, y1 - h * 0.42), (cx + tw / 2, y1 - 4)], fill=accent)
        d.polygon(
            [(cx - tw * 0.1, y1 - 4), (cx, y1 - h * 0.2), (cx + tw * 0.1, y1 - 4)],
            fill=mix(accent, "#000000", 0.45),
        )
    else:  # cup
        cw = w * 0.5
        top = y0 + h * 0.36
        d.rounded_rectangle(
            (cx - cw / 2, top, cx + cw / 2, y1 - h * 0.04),
            radius=int(cw * 0.22),
            fill=mix(ink, "#FFFFFF", 0.1),
        )
        d.ellipse(
            (cx + cw * 0.38, top + h * 0.12, cx + cw * 0.72, top + h * 0.38),
            outline=mix(ink, "#FFFFFF", 0.1),
            width=int(cw * 0.07),
        )
        d.ellipse((cx - cw * 0.44, top - h * 0.04, cx + cw * 0.44, top + h * 0.06), fill=accent)
        for i in range(3):
            sx = cx - cw * 0.2 + i * cw * 0.2
            d.arc(
                (sx - 18, top - h * 0.3, sx + 18, top - h * 0.08),
                100,
                260,
                fill=mix(bg, "#FFFFFF", 0.4),
                width=5,
            )
    rng = random.Random(seed)
    for _ in range(5):  # sparkle / texture dots
        rx, ry = rng.uniform(x0, x1), rng.uniform(y0, y1 - h * 0.3)
        r = rng.uniform(3, 7)
        d.ellipse((rx - r, ry - r, rx + r, ry + r), fill=mix(accent, "#FFFFFF", 0.55))


def wrap(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width=width) or [""]


def creative(brand: Brand, concept: Concept, seed: int, path: Path) -> None:
    """540×675 (4:5) generated creative: background, product illustration, headline, layout extras."""
    W, H = 540, 675
    bg, accent, ink = brand.palette
    dark_bg = sum(hex_rgb(bg)) < 380
    text_col = hex_rgb(ink if not dark_bg else ink)
    img = Image.new("RGBA", (W, H), hex_rgb(bg) + (255,))
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for i in range(H):
        t = i / H
        gd.line([(0, i), (W, i)], fill=mix(bg, accent, 0.18 * t) + (255,))
    img.alpha_composite(grad)
    d = ImageDraw.Draw(img)
    rng = random.Random(seed)
    d.ellipse((W * 0.45, -W * 0.25, W * 1.3, W * 0.55), fill=mix(bg, accent, 0.28 + rng.random() * 0.1))

    layout = concept.layout
    head = concept.headline
    if layout == "split":
        d.rectangle((0, 0, W / 2, H), fill=mix(bg, ink, 0.08))
        draw_product(img, brand.product, (40, 250, W / 2 - 20, 600), brand, seed)
        y = 120
        for line in wrap(head, 12):
            d.text((W / 2 + 24, y), line, font=font(34), fill=text_col)
            y += 42
        d.text((W / 2 + 24, y + 16), brand.name, font=font(18, False), fill=hex_rgb(accent))
    elif layout == "quote":
        d.text((40, 60), "“", font=font(120), fill=hex_rgb(accent))
        y = 170
        for line in wrap(concept.hook, 24):
            d.text((44, y), line, font=font(28), fill=text_col)
            y += 36
        stars_y = y + 18
        for i in range(5):
            cx = 56 + i * 34
            pts = [
                (cx + 13 * math.cos(math.radians(a)), stars_y + 13 * math.sin(math.radians(a)))
                for a in range(-90, 270, 36)
            ]
            pts = [
                (
                    pts[j]
                    if j % 2 == 0
                    else ((pts[j][0] - cx) * 0.45 + cx, (pts[j][1] - stars_y) * 0.45 + stars_y)
                )
                for j in range(10)
            ]
            d.polygon(pts, fill=hex_rgb(accent))
        draw_product(img, brand.product, (W * 0.5, H * 0.58, W - 30, H - 40), brand, seed)
    elif layout == "offer":
        draw_product(img, brand.product, (W * 0.2, 250, W * 0.8, 620), brand, seed)
        r = 92
        d.ellipse((W - r * 2 - 26, 40, W - 26, 40 + r * 2), fill=hex_rgb(accent))
        label = (concept.offer or "Offer").split(" ")
        oy = 40 + r - (len(label[:3]) * 30) / 2
        for word in label[:3]:
            d.text(
                (W - r - 26, oy + 14),
                word.upper(),
                font=font(26),
                fill=mix(ink, "#000000", 0.2) if not dark_bg else hex_rgb(bg),
                anchor="mm",
            )
            oy += 30
        y = 60
        for line in wrap(head, 14)[:3]:
            d.text((36, y), line, font=font(34), fill=text_col)
            y += 42
    elif layout == "grid":
        for i in range(3):
            x = 24 + i * 168
            d.rounded_rectangle(
                (x, 300, x + 156, 560), radius=18, fill=mix(bg, "#FFFFFF" if not dark_bg else "#000000", 0.35)
            )
            draw_product(img, brand.product, (x + 18, 330, x + 138, 540), brand, seed + i)
        y = 70
        for line in wrap(head, 18):
            d.text((W / 2, y), line, font=font(36), fill=text_col, anchor="mt")
            y += 44
        for i in range(3):
            d.ellipse(
                (W / 2 - 30 + i * 24, 610, W / 2 - 18 + i * 24, 622),
                fill=hex_rgb(accent) if i == 0 else mix(bg, ink, 0.3),
            )
    else:  # hero
        y = 54
        for line in wrap(head, 16):
            d.text((W / 2, y), line, font=font(40), fill=text_col, anchor="mt")
            y += 48
        draw_product(img, brand.product, (W * 0.22, y + 40, W * 0.78, H - 50), brand, seed)

    if concept.media == "video":
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.ellipse((W / 2 - 44, H / 2 - 44, W / 2 + 44, H / 2 + 44), fill=(0, 0, 0, 120))
        od.polygon(
            [(W / 2 - 14, H / 2 - 22), (W / 2 - 14, H / 2 + 22), (W / 2 + 24, H / 2)],
            fill=(255, 255, 255, 235),
        )
        img.alpha_composite(overlay)
    d = ImageDraw.Draw(img)
    d.text((W - 14, H - 12), "FICTIONAL DEMO", font=font(11, False), fill=mix(bg, ink, 0.45), anchor="rb")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, "JPEG", quality=86)


def logo(brand: Brand, path: Path, size: int = 160) -> None:
    bg, accent, ink = brand.palette
    img = Image.new("RGB", (size, size), hex_rgb(accent if sum(hex_rgb(bg)) > 380 else bg))
    d = ImageDraw.Draw(img)
    initials = "".join(w[0] for w in brand.name.split()[:2])
    fg = hex_rgb("#FFFFFF") if sum(hex_rgb(bg)) > 380 else hex_rgb(accent)
    d.text((size / 2, size / 2), initials, font=font(int(size * 0.42)), fill=fg, anchor="mm")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")


def landing(brand: Brand, title: str, path: Path) -> None:
    W, H = 1366, 900
    bg, accent, ink = brand.palette
    dark = sum(hex_rgb(bg)) < 380
    img = Image.new("RGBA", (W, H), hex_rgb("#FFFFFF") + (255,))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 72), fill=hex_rgb(bg))
    d.text(
        (48, 36), brand.name, font=font(26), fill=hex_rgb(ink) if not dark else hex_rgb(accent), anchor="lm"
    )
    for i, item in enumerate(["Shop", "Routine", "Reviews", "About"]):
        d.text(
            (W - 460 + i * 105, 36),
            item,
            font=font(18, False),
            fill=hex_rgb(ink) if not dark else hex_rgb("#FFFFFF"),
            anchor="lm",
        )
    d.rectangle((0, 72, W, 600), fill=mix(bg, "#FFFFFF", 0.35 if not dark else 0.05))
    y = 190
    for line in wrap(title, 22):
        d.text((90, y), line, font=font(54), fill=hex_rgb(ink) if not dark else hex_rgb("#FFFFFF"))
        y += 64
    d.text(
        (92, y + 20),
        brand.tagline,
        font=font(22, False),
        fill=mix(ink, "#888888", 0.4) if not dark else hex_rgb("#DDDDDD"),
    )
    d.rounded_rectangle((92, y + 80, 330, y + 140), radius=30, fill=hex_rgb(accent))
    d.text((211, y + 110), "Shop now", font=font(22), fill=hex_rgb("#FFFFFF"), anchor="mm")
    draw_product(img, brand.product, (W * 0.58, 130, W * 0.9, 580), brand, 7)
    for i in range(3):
        x = 90 + i * 410
        d.rounded_rectangle((x, 650, x + 370, 860), radius=20, fill=hex_rgb("#F4F4F7"))
        d.text(
            (x + 28, 690),
            ["Free shipping", "30-day returns", "4.8 / 5 rating"][i],
            font=font(24),
            fill=hex_rgb("#222222"),
        )
        d.text((x + 28, 735), "Fictional demo page", font=font(18, False), fill=hex_rgb("#888888"))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, "PNG", optimize=True)


# ----------------------------------------------------------------------------- dataset
@dataclass
class DemoAd:
    library_id: str
    concept: Concept
    concept_idx: int
    variant: int
    start: date
    end: date | None
    platforms: list[str]
    copy: str
    headline: str
    landing_url: str
    thumb_rel: str
    variations_by_scan: list[int]


def demo_rate() -> float:
    """Ads per minute measured by real scans (docs/benchmarks.json); a cautious fallback otherwise."""
    try:
        data = json.loads((ROOT / "docs" / "benchmarks.json").read_text(encoding="utf-8"))
        rate = float(data["summary"]["ads_per_minute"])
        return rate if rate > 0 else 120.0
    except (OSError, KeyError, ValueError, TypeError):
        return 120.0


def build_ads(brand: Brand, brand_idx: int, slug: str) -> list[DemoAd]:
    ads: list[DemoAd] = []
    counter = 0
    for ci, c in enumerate(brand.concepts):
        lead_age = RNG.randint(*c.age)
        end = TODAY - timedelta(days=c.ended_days_ago) if c.ended_days_ago is not None else None
        thumb_rel = f"media/{slug}/c{ci:02d}.jpg"
        creative(brand, c, seed=brand_idx * 100 + ci, path=DEMO_DIR / thumb_rel)
        for v in range(c.variants):
            counter += 1
            age = max(lead_age - v * RNG.randint(2, 9), 1)
            start = TODAY - timedelta(days=age - 1)
            n_plat = RNG.choice([2, 3, 4, 4, 5]) if age > 30 else RNG.choice([1, 2, 2, 3])
            endings = [
                "",
                " Free shipping over $40.",
                " Limited stock.",
                " Ends Sunday.",
                " Join 10,000+ customers.",
                " Tap to see how.",
            ]
            body = c.body + endings[v % len(endings)]
            copy = f"{c.hook}\n\n{body}" + (f"\n\n{c.offer}." if c.offer and v % 2 == 0 else "")
            final_vars = 1 + (3 if c.variants >= 5 and v == 0 else RNG.choice([0, 0, 1, 2]))
            by_scan = [final_vars] * len(SCAN_DAYS_AGO)
            if c.scaled and v == 0:
                by_scan = [max(1, final_vars - 3), max(1, final_vars - 2), final_vars + 2]
            ads.append(
                DemoAd(
                    library_id=f"demo-{brand_idx}{ci:02d}{v:02d}{RNG.randint(100000, 999999)}",
                    concept=c,
                    concept_idx=ci,
                    variant=v,
                    start=start,
                    end=end if v < max(1, c.variants - 1) or end is None else None,
                    platforms=sorted(RNG.sample(PLATFORMS, n_plat), key=PLATFORMS.index),
                    copy=copy,
                    headline=c.headline,
                    landing_url=f"https://{brand.domain}/{['products/hero', 'pages/offer', 'pages/reviews'][ci % 3]}?utm_source=meta&utm_content={ci}-{v}",
                    thumb_rel=thumb_rel,
                    variations_by_scan=by_scan,
                )
            )
    return ads


def seed(make_pdf: bool) -> None:
    if DEMO_DIR.exists():
        shutil.rmtree(DEMO_DIR)
    DEMO_DIR.mkdir(parents=True)
    os.environ["ADSPY_DATA_DIR"] = str(DEMO_DIR)
    os.environ["ADSPY_DEMO"] = "1"

    from sqlmodel import select

    from app.analysis.changes import detect_changes
    from app.analysis.grouping import regroup_competitor
    from app.analysis.scoring import compute_score
    from app.core.config import save_override
    from app.core.paths import slugify
    from app.db.models import (
        Ad,
        AdAnalysis,
        AdSnapshot,
        Board,
        BoardItem,
        ChangeEvent,
        Client,
        Competitor,
        LandingPage,
        Scan,
        WatchlistItem,
    )
    from app.db.session import run_migrations, session_scope
    from app.jobs.scheduler import compute_next_run
    from app.scraper.landing import url_key

    run_migrations()
    rate = demo_rate()
    print(f"Seeding {DEMO_DIR} (scan timings use {rate:g} ads/min)")

    # Demo branding for reports.
    agency = Brand("Brightline Creative", "", ("#0B0B12", "#A78BFA", "#FFFFFF"), "bottle", "")
    logo_rel = "media/_branding/logo-demo.png"
    img = Image.new("RGBA", (420, 120), (0, 0, 0, 0))
    ld = ImageDraw.Draw(img)
    ld.rounded_rectangle((0, 14, 92, 106), radius=24, fill=hex_rgb("#A78BFA"))
    ld.text((46, 60), "B", font=font(56), fill=hex_rgb("#0B0B12"), anchor="mm")
    ld.text((112, 60), "Brightline", font=font(44), fill=hex_rgb("#FFFFFF"), anchor="lm")
    (DEMO_DIR / logo_rel).parent.mkdir(parents=True, exist_ok=True)
    img.save(DEMO_DIR / logo_rel)
    save_override({"reports": {"agency_name": agency.name, "logo_path": logo_rel}})

    comp_ids: dict[str, int] = {}
    with session_scope() as session:
        for bi, brand in enumerate(BRANDS, 1):
            slug = slugify(brand.name)
            logo(brand, DEMO_DIR / f"media/{slug}/logo.png")
            comp = Competitor(
                name=brand.name, slug=slug, page_id=f"demo-page-{bi}", logo_url=f"media/{slug}/logo.png"
            )
            session.add(comp)
            session.flush()
            comp_ids[brand.name] = comp.id  # type: ignore[assignment]
            demo_ads = build_ads(brand, bi, slug)
            rows: dict[str, Ad] = {}
            analysis_done: set[str] = set()

            for si, days_ago in enumerate(SCAN_DAYS_AGO):
                scan_day = TODAY - timedelta(days=days_ago)
                live = [a for a in demo_ads if a.start <= scan_day and (a.end is None or a.end >= scan_day)]
                started = datetime.combine(scan_day, time(9, RNG.randint(0, 20)), tzinfo=UTC) - timedelta(
                    hours=6
                )
                duration = len(live) / rate * 60 + RNG.uniform(6, 14)
                scan = Scan(
                    competitor_id=comp.id,  # type: ignore[arg-type]
                    query=brand.name,
                    search_type="keyword",
                    country="US",
                    exact_page=True,
                    max_ads=300,
                    status="completed",
                    total_results=len(live),
                    ads_found=len(live),
                    ads_processed=len(live),
                    created_at=started,
                    started_at=started,
                    finished_at=started + timedelta(seconds=duration),
                    trigger="manual" if si == 0 else "schedule",
                )
                session.add(scan)
                session.flush()
                for a in live:
                    end_or_day = min(a.end, scan_day) if a.end else scan_day
                    days = (end_or_day - a.start).days + 1
                    variations = a.variations_by_scan[si]
                    ad = rows.get(a.library_id)
                    if ad is None:
                        ad = Ad(
                            library_id=a.library_id,
                            competitor_id=comp.id,  # type: ignore[arg-type]
                            page_name=brand.name,
                            page_id=comp.page_id,
                            start_date=a.start,
                            platforms=a.platforms,
                            ad_copy=a.copy,
                            headline=a.headline,
                            cta_text=a.concept.cta,
                            cta_type=a.concept.cta.upper().replace(" ", "_"),
                            landing_url=a.landing_url,
                            display_format={
                                "image": "IMAGE",
                                "video": "VIDEO",
                                "carousel": "CAROUSEL",
                                "dynamic": "DCO",
                            }[a.concept.media],
                            media_type=a.concept.media,
                            thumbnail_path=a.thumb_rel,
                            media_paths=[a.thumb_rel],
                            first_seen_at=started,
                            source="demo",
                        )
                        session.add(ad)
                        rows[a.library_id] = ad
                    ad.status = "active"
                    ad.days_running = days
                    ad.variation_count = variations
                    ad.last_seen_at = started
                    ad.score, ad.score_breakdown = compute_score(days, variations, a.platforms, True)
                    session.flush()
                    ad.last_scan_id = scan.id
                    session.add(
                        AdSnapshot(
                            ad_id=ad.id,  # type: ignore[arg-type]
                            scan_id=scan.id,  # type: ignore[arg-type]
                            status="active",
                            variation_count=variations,
                            days_running=days,
                            score=ad.score,
                            captured_at=started,
                        )
                    )
                session.flush()
                detect_changes(session, scan.id)  # type: ignore[arg-type]
                session.flush()
                for ev in session.exec(select(ChangeEvent).where(ChangeEvent.scan_id == scan.id)).all():
                    ev.created_at = scan.finished_at  # type: ignore[assignment]
                    session.add(ev)
                comp.last_scan_at = scan.finished_at

            # Ads that ended after the last scan still look active; mark ones whose end passed.
            for a in demo_ads:
                ad = rows.get(a.library_id)
                if ad is not None and a.end is not None and a.end < TODAY and ad.status == "active":
                    ad.status, ad.end_date = "inactive", a.end
                    ad.score, ad.score_breakdown = compute_score(
                        ad.days_running, ad.variation_count, ad.platforms, False
                    )

            # AI-style analysis for most ads (clearly labelled as demo).
            for a in demo_ads:
                ad = rows.get(a.library_id)
                if ad is None or a.library_id in analysis_done or RNG.random() < 0.2:
                    continue
                c = a.concept
                session.add(
                    AdAnalysis(
                        library_id=a.library_id,
                        ad_id=ad.id,
                        model="demo-dataset",
                        hook_type=c.hook_type,
                        hook_text=c.hook,
                        angle=c.angle,
                        emotion=c.emotion,
                        offer=c.offer,
                        cta=c.cta,
                        target_audience_guess={
                            "bottle": "women 25–40 with sensitive skin",
                            "jar": "adults with dry, reactive skin",
                            "mountain": "thru-hikers and ultralight backpackers",
                            "cup": "home espresso enthusiasts",
                        }[brand.product],
                        one_line_summary=f"{brand.name} uses {c.angle} to sell {brand.tagline.lower()}.",
                        what_to_steal=c.steal or None,
                    )
                )
                analysis_done.add(a.library_id)

            # Landing pages (one per destination path).
            seen: set[str] = set()
            for a in demo_ads:
                key = url_key(a.landing_url)
                if not key or key in seen:
                    continue
                seen.add(key)
                rel = f"media/{slug}/landing/{len(seen)}.png"
                landing(brand, a.concept.headline, DEMO_DIR / rel)
                session.add(
                    LandingPage(
                        url_key=key,
                        url=a.landing_url,
                        final_url=key,
                        title=f"{a.concept.headline} | {brand.name}",
                        screenshot_path=rel,
                        status="ok",
                    )
                )
            session.commit()
            regroup_competitor(session, comp.id)  # type: ignore[arg-type]
            session.commit()
            print(f"  {brand.name}: {len(rows)} ads, {len(brand.concepts)} concepts")

        # Clients
        for name, notes, members in CLIENTS:
            client = Client(name=name, notes=notes)
            session.add(client)
            session.flush()
            for m in members:
                comp = session.get(Competitor, comp_ids[m])
                comp.client_id = client.id  # type: ignore[union-attr]
                session.add(comp)
        session.commit()
        clients = {c.name: c.id for c in session.exec(select(Client)).all()}

        # Watchlist
        for name, freq, hour, weekday in [
            ("Lumen Skincare", "daily", 9, 0),
            ("Northpeak Outdoor", "weekly", 8, 0),
            ("Brewlab Coffee", "daily", 7, 0),
        ]:
            last = session.exec(select(Scan).where(Scan.competitor_id == comp_ids[name]).order_by(Scan.id.desc())).first()  # type: ignore[union-attr]
            item = WatchlistItem(
                competitor_id=comp_ids[name],
                query=name,
                exact_page=True,
                max_ads=300,
                frequency=freq,
                hour=hour,
                weekday=weekday,
                last_run_at=last.finished_at if last else None,
                last_scan_id=last.id if last else None,
            )
            item.next_run_at = compute_next_run(item)
            session.add(item)

        # Swipe files
        def top(brand: str, n: int, media: str | None = None) -> list[Ad]:
            stmt = select(Ad).where(Ad.competitor_id == comp_ids[brand])
            if media:
                stmt = stmt.where(Ad.media_type == media)
            return list(session.exec(stmt.order_by(Ad.score.desc())).all())[:n]  # type: ignore[attr-defined]

        boards = [
            (
                "Hooks that stop the scroll",
                "Openers to adapt for Solace Skin's serum launch",
                clients["Solace Skin"],
                [
                    (
                        top("Lumen Skincare", 3),
                        ["hook", "social proof"],
                        "Specific numbers in the first line. Test a review-count hook.",
                    ),
                    (
                        top("Dewdrop Labs", 2),
                        ["hook", "problem"],
                        "Names the sensation before the cause. Strong for barrier-repair messaging.",
                    ),
                ],
            ),
            (
                "Offer structures",
                "How competitors frame discounts and guarantees",
                None,
                [
                    (
                        [a for a in top("Brewlab Coffee", 6) if a.cta_text == "Sign up"][:2]
                        + top("Northpeak Outdoor", 1),
                        ["offer"],
                        "Removes risk instead of cutting price.",
                    ),
                    (
                        [a for a in top("Lumen Skincare", 12) if "%" in (a.headline or "")][:2],
                        ["offer", "discount"],
                        None,
                    ),
                ],
            ),
            (
                "Outdoor UGC references",
                "Story-led video ads",
                None,
                [
                    (
                        top("Northpeak Outdoor", 3, "video"),
                        ["ugc", "video"],
                        "Real journeys, worn gear. Shoot this style for the spring campaign.",
                    )
                ],
            ),
        ]
        for name, desc, client_id, groups in boards:
            board = Board(name=name, description=desc, client_id=client_id)
            session.add(board)
            session.flush()
            used: set[int] = set()
            for ads, tags, note in groups:
                for i, ad in enumerate(ads):
                    if ad.id in used:
                        continue
                    used.add(ad.id)  # type: ignore[arg-type]
                    saved = datetime.now(UTC) - timedelta(days=RNG.randint(1, 12), hours=RNG.randint(0, 20))
                    session.add(BoardItem(board_id=board.id, ad_id=ad.id, tags=tags, note=note if i == 0 else None, added_at=saved))  # type: ignore[arg-type]
        session.commit()

    # Sample reports (HTML + PDF) generated by the real report builder.
    from app.db.models import Report
    from app.reports.builder import DEFAULT_SECTIONS, ReportSpec, render_report
    from app.scraper.media import relative_to_data

    for kind, title, ids, client_name, client_id in [
        (
            "client",
            "Solace Skin: competitor landscape",
            [comp_ids["Lumen Skincare"], comp_ids["Dewdrop Labs"]],
            "Solace Skin",
            clients["Solace Skin"],
        ),
        (
            "compare",
            None,
            [comp_ids["Lumen Skincare"], comp_ids["Northpeak Outdoor"], comp_ids["Brewlab Coffee"]],
            None,
            None,
        ),
    ]:
        spec = ReportSpec(
            competitor_ids=ids, title=title, client_name=client_name, sections=list(DEFAULT_SECTIONS)
        )
        html, meta = render_report(spec)
        report = Report(
            title=spec.title or " vs ".join(b.name for b in BRANDS if comp_ids[b.name] in ids),
            kind=kind,
            competitor_ids=ids,
            options={
                "sections": spec.sections,
                "top_n": spec.top_n,
                "client_name": client_name,
                "client_id": client_id,
                "ai": False,
                "own_only": True,
                **meta,
            },
            html_path=relative_to_data(html),
        )
        if make_pdf:
            try:
                from app.reports.pdf import html_to_pdf

                report.pdf_path = relative_to_data(html_to_pdf(html, html.with_suffix(".pdf")))
            except Exception as exc:  # noqa: BLE001
                print(f"  PDF skipped ({exc})")
        with session_scope() as session:
            session.add(report)
            session.commit()
        print(f"  Report: {report.title}")
    print("Done. Run: python backend/run.py --demo")


def main() -> int:
    ap = argparse.ArgumentParser(description="Create the fictional demo dataset in data-demo/.")
    ap.add_argument("--no-pdf", action="store_true", help="Skip PDF export of the sample reports")
    args = ap.parse_args()
    seed(make_pdf=not args.no_pdf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
