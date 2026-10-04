"""Variation grouping: cluster a competitor's ads that share a creative or near-identical copy.

Two ads join the same group when either
  * their thumbnails' perceptual hashes (pHash) differ by <= PHASH_DISTANCE bits, or
  * their normalized copy is identical / near-identical (SequenceMatcher >= COPY_SIMILARITY).

Each group is summarized as "N creatives · M copy tests" (distinct images × distinct texts).
Candidate pairs are found with banded LSH so this stays fast for thousands of ads.
"""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import imagehash
from PIL import Image, UnidentifiedImageError
from sqlmodel import Session, select

from app.core.paths import data_dir
from app.db.models import Ad

log = logging.getLogger(__name__)

PHASH_DISTANCE = 6
COPY_SIMILARITY = 0.92
BANDS = 8  # 64-bit hash → 8 bands of 8 bits; distance ≤ 6 guarantees ≥ 2 identical bands


# ----------------------------------------------------------------------------- features
def normalize_copy(text: str | None) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"\{\{[^}]*\}\}", " ", text)
    text = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text)
    return re.sub(r"\s+", " ", text).strip()


def copy_hash(text: str | None) -> str | None:
    norm = normalize_copy(text)
    return hashlib.sha1(norm.encode()).hexdigest()[:16] if len(norm) >= 8 else None


def image_phash(path: Path) -> str | None:
    try:
        with Image.open(path) as img:
            return str(imagehash.phash(img.convert("RGB")))
    except (OSError, UnidentifiedImageError, ValueError):
        log.debug("Could not hash %s", path)
        return None


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def ensure_features(ad: Ad) -> bool:
    """Compute pHash / copy hash when missing. Returns True if anything changed."""
    changed = False
    if ad.phash is None:
        source = ad.thumbnail_path or (ad.media_paths or [None])[0]
        if source and not source.endswith(".mp4"):
            path = data_dir() / source
            if path.exists():
                ad.phash = image_phash(path)
                changed = ad.phash is not None
    text_hash = copy_hash(" ".join(filter(None, [ad.ad_copy, ad.headline])))
    if text_hash != ad.copy_hash:
        ad.copy_hash = text_hash
        changed = True
    return changed


# ----------------------------------------------------------------------------- clustering
class UnionFind:
    def __init__(self, items: list[int]) -> None:
        self.parent = {i: i for i in items}

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def cluster(ads: list[Ad]) -> dict[int, list[Ad]]:
    """Return {root ad id: [ads in group]} for the given ads."""
    by_id = {a.id: a for a in ads if a.id is not None}
    uf = UnionFind(list(by_id))

    # 1) Same creative: banded LSH over the 64-bit pHash, then exact distance check.
    buckets: dict[tuple[int, str], list[int]] = defaultdict(list)
    for ad_id, ad in by_id.items():
        if ad.phash and len(ad.phash) == 16:
            for band in range(BANDS):
                buckets[(band, ad.phash[band * 2 : band * 2 + 2])].append(ad_id)
    checked: set[tuple[int, int]] = set()
    for members in buckets.values():
        if len(members) < 2 or len(members) > 400:  # a huge bucket = a degenerate (blank) image
            continue
        for i, a in enumerate(members):
            for b in members[i + 1 :]:
                pair = (a, b) if a < b else (b, a)
                if pair in checked:
                    continue
                checked.add(pair)
                if hamming(by_id[a].phash, by_id[b].phash) <= PHASH_DISTANCE:  # type: ignore[arg-type]
                    uf.union(a, b)

    # 2) Same copy: exact normalized hash, then near-duplicates within a "first words" block.
    by_hash: dict[str, list[int]] = defaultdict(list)
    blocks: dict[str, list[int]] = defaultdict(list)
    norms: dict[int, str] = {}
    for ad_id, ad in by_id.items():
        if ad.copy_hash:
            by_hash[ad.copy_hash].append(ad_id)
            norm = normalize_copy(" ".join(filter(None, [ad.ad_copy, ad.headline])))
            norms[ad_id] = norm
            blocks[" ".join(norm.split()[:3])].append(ad_id)
    for members in by_hash.values():
        for other in members[1:]:
            uf.union(members[0], other)
    for members in blocks.values():
        if len(members) < 2 or len(members) > 200:
            continue
        for i, a in enumerate(members):
            for b in members[i + 1 :]:
                if uf.find(a) == uf.find(b):
                    continue
                if SequenceMatcher(None, norms[a], norms[b]).ratio() >= COPY_SIMILARITY:
                    uf.union(a, b)

    groups: dict[int, list[Ad]] = defaultdict(list)
    for ad_id, ad in by_id.items():
        groups[uf.find(ad_id)].append(ad)
    return groups


def distinct_creatives(members: list[Ad]) -> int:
    reps: list[str] = []
    unhashed = 0
    for ad in members:
        if not ad.phash:
            unhashed += 1
            continue
        if not any(hamming(ad.phash, r) <= PHASH_DISTANCE for r in reps):
            reps.append(ad.phash)
    return max(1, len(reps) + (1 if unhashed and not reps else 0))


def regroup_competitor(session: Session, competitor_id: int) -> dict[str, int]:
    """Recompute features and groups for one competitor. Caller commits."""
    ads = list(session.exec(select(Ad).where(Ad.competitor_id == competitor_id)).all())
    hashed = sum(1 for ad in ads if ensure_features(ad))
    groups = cluster(ads)
    multi = 0
    for root, members in groups.items():
        size = len(members)
        creatives = distinct_creatives(members)
        copies = len({m.copy_hash or f"none-{m.id}" for m in members})
        multi += int(size > 1)
        for ad in members:
            ad.group_key = f"{competitor_id}-{root}"
            ad.group_size = size
            ad.group_creatives = creatives
            ad.group_copies = copies
            session.add(ad)
    log.info(
        "Grouped %d ads into %d groups (%d with variations, %d newly hashed)",
        len(ads),
        len(groups),
        multi,
        hashed,
    )
    return {"ads": len(ads), "groups": len(groups), "multi": multi, "hashed": hashed}


def group_label(creatives: int, copies: int) -> str:
    c = f"{creatives} creative{'s' if creatives != 1 else ''}"
    t = f"{copies} copy test{'s' if copies != 1 else ''}"
    return f"{c} · {t}"
