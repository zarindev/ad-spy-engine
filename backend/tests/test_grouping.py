from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from app.analysis.grouping import (
    cluster,
    copy_hash,
    distinct_creatives,
    group_label,
    image_phash,
    normalize_copy,
)
from app.db.models import Ad


def make_image(path: Path, shape: str, shift: int = 0) -> str:
    img = Image.new("RGB", (256, 256), "white")
    d = ImageDraw.Draw(img)
    if shape == "circle":
        d.ellipse((40 + shift, 40, 200 + shift, 200), fill="black")
    else:
        d.rectangle((20, 120, 236, 160), fill="black")
        d.rectangle((120, 20, 160, 236), fill="navy")
    img.save(path)
    return image_phash(path)  # type: ignore[return-value]


def ad(i: int, copy: str | None, phash: str | None) -> Ad:
    a = Ad(id=i, library_id=str(i), competitor_id=1, ad_copy=copy, phash=phash)
    a.copy_hash = copy_hash(copy)
    return a


def test_normalize_copy():
    assert normalize_copy("Shop NOW!! 🔥 https://x.com/a {{product.name}}") == "shop now"
    assert copy_hash("Hi") is None  # too short to be meaningful
    assert copy_hash("Shop the sale now!") == copy_hash("shop the SALE now")


def test_same_creative_and_same_copy_cluster(tmp_path):
    circle = make_image(tmp_path / "a.png", "circle")
    circle2 = make_image(tmp_path / "b.png", "circle", shift=2)  # re-encoded / nudged copy
    cross = make_image(tmp_path / "c.png", "cross")
    ads = [
        ad(1, "Our best protein shake yet, now in chocolate", circle),
        ad(2, "Totally different words about breakfast routines", circle2),  # same image → same group
        ad(3, "Our best protein shake yet, now in chocolate!", cross),  # same copy → same group
        ad(4, "Unrelated ad about running shoes and trails", None),
    ]
    groups = cluster(ads)
    sizes = sorted(len(g) for g in groups.values())
    assert sizes == [1, 3]
    big = max(groups.values(), key=len)
    assert {a.id for a in big} == {1, 2, 3}
    assert distinct_creatives(big) == 2


def test_near_identical_copy():
    ads = [
        ad(1, "Get 40g of protein before 9am with our new breakfast shake today", None),
        ad(2, "Get 40g of protein before 9am with our new breakfast shake now", None),
    ]
    assert len(cluster(ads)) == 1


def test_group_label():
    assert group_label(1, 6) == "1 creative · 6 copy tests"
    assert group_label(3, 1) == "3 creatives · 1 copy test"
