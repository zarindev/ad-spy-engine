"""Refresh parser test fixtures from the live Meta Ad Library.

Run this when Meta changes its markup and tests need new real-world samples:

    python scripts/capture_fixtures.py                       # default: Gymshark brand page
    python scripts/capture_fixtures.py --page-id 1234567890 --name acme

Saves (gzipped, to keep the repo small) into backend/tests/fixtures/:
    <name>_page.html.gz       full page HTML after a few scrolls (server JSON + rendered cards)
    <name>_xhr.json.gz        intercepted /api/graphql/ pagination payloads (list of strings)
    <name>_card_<fmt>.html    one rendered ad card per display format (DOM fallback tests)
    no_results_page.html.gz   a search that returns nothing

Only use brand pages here — fixtures are committed, so avoid private individuals' ads.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_selectors  # noqa: E402
from app.scraper.ad_library import FIND_CARDS_JS, ScanParams, build_search_url  # noqa: E402
from app.scraper.driver import create_driver, safe_quit  # noqa: E402
from app.scraper.parser import extract_nodes_from_html, extract_nodes_from_payload  # noqa: E402

FIXTURES = ROOT / "backend" / "tests" / "fixtures"


def write_gz(path: Path, text: str) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(text)
    print(f"  wrote {path.relative_to(ROOT)} ({path.stat().st_size / 1024:.0f} KB)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-id", default="129669023798560", help="Facebook Page ID (default: Gymshark)")
    ap.add_argument("--name", default="gymshark")
    ap.add_argument("--scrolls", type=int, default=3)
    args = ap.parse_args()
    FIXTURES.mkdir(parents=True, exist_ok=True)
    sel = get_selectors()

    driver = create_driver(headless=True)
    try:
        url = build_search_url(ScanParams(query=args.page_id, search_type="page_id"))
        print(f"Opening {url}")
        driver.get(url)
        time.sleep(7)
        for _ in range(args.scrolls):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(3)
        xhr = driver.execute_script("return window.__adspy || []")
        anchor = sel["anchors"]["card_xpath_anchor"]
        cards = driver.execute_script(FIND_CARDS_JS, anchor, sel["anchors"]["library_id"][0])
        html = driver.page_source

        write_gz(FIXTURES / f"{args.name}_page.html.gz", html)
        write_gz(FIXTURES / f"{args.name}_xhr.json.gz", json.dumps(xhr))

        nodes = {n["ad_archive_id"]: n for n in extract_nodes_from_html(html)}
        for payload in xhr:
            nodes.update({n["ad_archive_id"]: n for n in extract_nodes_from_payload(payload)})
        saved: set[str] = set()
        for card in cards:
            node = nodes.get(card["id"])
            fmt = (node or {}).get("snapshot", {}).get("display_format", "unknown").lower()
            if fmt in saved:
                continue
            saved.add(fmt)
            out = FIXTURES / f"{args.name}_card_{fmt}.html"
            out.write_text(card["html"], encoding="utf-8")
            (FIXTURES / f"{args.name}_card_{fmt}.expected.json").write_text(
                json.dumps(node, indent=1, ensure_ascii=False), encoding="utf-8"
            )
            print(f"  wrote {out.relative_to(ROOT)} (+ expected JSON)")

        driver.get(build_search_url(ScanParams(query="zqxjv qpwzk nonexistentbrand")))
        time.sleep(6)
        write_gz(FIXTURES / "no_results_page.html.gz", driver.page_source)
    finally:
        safe_quit(driver)


if __name__ == "__main__":
    main()
