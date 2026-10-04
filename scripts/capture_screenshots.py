"""Capture every screen of the app (demo dataset) at 1440×900, light and dark.

    python scripts/seed_demo.py              # once, creates data-demo/
    python scripts/capture_screenshots.py    # writes docs/assets/screenshots/*.png

Starts its own server in --demo mode on a spare port (so only fictional brands appear), drives
it with headless Chrome and stops it again. Screenshots are of this app's own UI only.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets" / "screenshots"

# name, path, optional action after load
SCREENS: list[tuple[str, str, str | None]] = [
    ("dashboard", "/", None),
    ("new-scan", "/scan/new", None),
    ("scan", "/scans/{last_scan}", None),
    ("results", "/ads", None),
    ("ad-detail", "/ads", "open_first_ad"),
    ("competitors", "/competitors", None),
    ("competitor-profile", "/competitors/1", None),
    ("compare", "/compare?ids=1,3,4", None),
    ("watchlist", "/watchlist", None),
    ("swipe-file", "/boards/1", None),
    ("reports", "/reports", "open_preview"),
    ("settings", "/settings", None),
]


def wait_for(url: str, timeout: float = 30) -> None:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:  # noqa: S310 — localhost only
                if r.status == 200:
                    return
        except OSError:
            time.sleep(0.5)
    raise SystemExit(f"Server did not start: {url}")


def until(fn, timeout: float = 12.0):  # noqa: ANN001, ANN201
    """Poll until fn() returns something truthy (Selenium lookups that may not exist yet)."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            value = fn()
            if value:
                return value
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.3)
    raise RuntimeError(f"Timed out waiting for the page: {getattr(fn, '__name__', fn)}")


def fetch_json(url: str):  # noqa: ANN201
    import json

    with urllib.request.urlopen(url, timeout=5) as r:  # noqa: S310
        return json.loads(r.read())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--only", nargs="*", help="screen names to capture")
    ap.add_argument("--themes", nargs="*", default=["dark", "light"])
    args = ap.parse_args()
    if not (ROOT / "data-demo" / "app.db").exists():
        raise SystemExit("No demo dataset. Run: python scripts/seed_demo.py")
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        raise SystemExit("Frontend not built. Run: cd frontend && npm run build")

    base = f"http://127.0.0.1:{args.port}"
    server = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "backend" / "run.py"),
            "--demo",
            "--no-browser",
            "--port",
            str(args.port),
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    try:
        wait_for(f"{base}/api/health")
        if not fetch_json(f"{base}/api/health").get("demo"):
            raise SystemExit("Server is not in demo mode; refusing to screenshot real data.")
        last_scan = fetch_json(f"{base}/api/scans?limit=1")["items"][0]["id"]

        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1440,900")
        opts.add_argument("--force-device-scale-factor=1")
        opts.add_argument("--hide-scrollbars")
        driver = webdriver.Chrome(options=opts)
        OUT.mkdir(parents=True, exist_ok=True)
        try:
            for theme in args.themes:
                driver.get(base + "/")
                driver.execute_script(
                    "localStorage.setItem('adspy-theme', arguments[0]);"
                    "localStorage.setItem('adspy-sidebar-collapsed', 'false');",
                    theme,
                )
                for name, path, action in SCREENS:
                    if args.only and name not in args.only:
                        continue
                    print(f"  {name} ({theme})…", end=" ", flush=True)
                    driver.get(base + path.format(last_scan=last_scan))
                    # wait for skeletons to disappear, then let images and animations settle
                    for attempt in range(2):  # one reload if the SPA didn't settle
                        try:
                            until(
                                lambda: len(
                                    driver.execute_script(
                                        "return document.querySelector('main')?.innerText || ''"
                                    )
                                )
                                > 40
                            )
                            until(lambda: not driver.find_elements(By.CSS_SELECTOR, "main .skeleton"), 15)
                            break
                        except RuntimeError:
                            if attempt:
                                raise
                            driver.refresh()
                    time.sleep(1.8)
                    if action == "open_first_ad":
                        until(lambda: driver.find_elements(By.CSS_SELECTOR, "article button"))[0].click()
                        until(lambda: driver.find_elements(By.CSS_SELECTOR, "[role=dialog] img"))
                        time.sleep(2.0)
                    elif action == "open_preview":
                        until(
                            lambda: [
                                b for b in driver.find_elements(By.TAG_NAME, "button") if b.text == "Preview"
                            ]
                        )[0].click()
                        until(lambda: driver.find_elements(By.CSS_SELECTOR, "iframe[title='Report preview']"))
                        time.sleep(3.0)
                    driver.execute_script("document.activeElement && document.activeElement.blur()")
                    target = OUT / f"{name}-{theme}.png"
                    driver.save_screenshot(str(target))
                    print(target.relative_to(ROOT))
        finally:
            driver.quit()
    finally:
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
