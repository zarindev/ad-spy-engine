"""Record docs/assets/demo.gif: a scripted walkthrough of the demo dataset (fictional brands).

    python scripts/seed_demo.py         # once
    python scripts/record_demo_gif.py

Dashboard → Results Gallery → Ad Detail → Compare → Report preview, captured with headless Chrome.
Live scans are off in demo mode, so the GIF shows the product's screens, not a scan in progress.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets" / "demo.gif"
PORT = 8767
SIZE = (1200, 750)  # 1440×900 scaled down to keep the GIF small


def until(fn, timeout: float = 15.0):  # noqa: ANN001, ANN201
    end = time.time() + timeout
    while time.time() < end:
        try:
            value = fn()
            if value:
                return value
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.25)
    raise RuntimeError("Timed out waiting for the page")


class Recorder:
    def __init__(self, driver: webdriver.Chrome) -> None:
        self.driver = driver
        self.frames: list[tuple[Image.Image, int]] = []

    def snap(self, hold_ms: int = 120) -> None:
        img = Image.open(io.BytesIO(self.driver.get_screenshot_as_png())).convert("RGB")
        self.frames.append((img.resize(SIZE, Image.LANCZOS), hold_ms))

    def hold(self, ms: int) -> None:
        self.snap(ms)

    def smooth_scroll(self, selector: str | None, distance: int, steps: int = 10) -> None:
        for _ in range(steps):
            if selector:
                self.driver.execute_script(
                    "const el = document.querySelector(arguments[0]); if (el) el.scrollBy(0, arguments[1]);",
                    selector,
                    distance // steps,
                )
            else:
                self.driver.execute_script("window.scrollBy(0, arguments[0])", distance // steps)
            time.sleep(0.05)
            self.snap(90)

    def save(self, path: Path) -> None:
        # One shared adaptive palette keeps colors stable between frames and the file small.
        base = self.frames[0][0].quantize(colors=255, method=Image.Quantize.MEDIANCUT)
        frames = [f.quantize(palette=base, dither=Image.Dither.NONE) for f, _ in self.frames]
        durations = [d for _, d in self.frames]
        frames[0].save(
            path,
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0,
            optimize=True,
            disposal=1,
        )


def main() -> int:
    if not (ROOT / "data-demo" / "app.db").exists():
        raise SystemExit("No demo dataset. Run: python scripts/seed_demo.py")
    base = f"http://127.0.0.1:{PORT}"
    server = subprocess.Popen(
        [sys.executable, str(ROOT / "backend" / "run.py"), "--demo", "--no-browser", "--port", str(PORT)],
        cwd=ROOT,
        env=os.environ.copy(),
    )
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1440,900")
    opts.add_argument("--force-device-scale-factor=1")
    opts.add_argument("--hide-scrollbars")
    driver = None
    try:
        until(lambda: urllib.request.urlopen(f"{base}/api/health", timeout=2).status == 200, 30)  # noqa: S310
        driver = webdriver.Chrome(options=opts)
        rec = Recorder(driver)
        driver.get(base + "/")
        driver.execute_script("localStorage.setItem('adspy-theme', 'dark')")

        def open_page(path: str) -> None:
            driver.get(base + path)
            until(
                lambda: len(driver.execute_script("return document.querySelector('main')?.innerText || ''"))
                > 40
            )
            until(lambda: not driver.find_elements(By.CSS_SELECTOR, "main .skeleton"))
            time.sleep(1.2)

        # 1. Dashboard
        open_page("/")
        rec.hold(1800)
        # 2. Results gallery, scroll through winners
        open_page("/ads")
        rec.hold(1200)
        rec.smooth_scroll(None, 700, steps=12)
        rec.hold(600)
        driver.execute_script("window.scrollTo(0, 0)")
        time.sleep(0.3)
        # 3. Ad detail panel
        until(lambda: driver.find_elements(By.CSS_SELECTOR, "article button"))[0].click()
        until(lambda: driver.find_elements(By.CSS_SELECTOR, "[role=dialog] img"))
        for _ in range(6):  # slide-in animation
            rec.snap(70)
        time.sleep(0.8)
        rec.hold(1600)
        rec.smooth_scroll("[role=dialog] .overflow-y-auto", 650, steps=10)
        rec.hold(1400)
        # 4. Compare
        open_page("/compare?ids=1,3,4")
        rec.hold(1500)
        rec.smooth_scroll(None, 900, steps=14)
        rec.hold(1300)
        # 5. Report preview
        open_page("/reports")
        until(lambda: [b for b in driver.find_elements(By.TAG_NAME, "button") if b.text == "Preview"])[
            0
        ].click()
        until(lambda: driver.find_elements(By.CSS_SELECTOR, "iframe[title='Report preview']"))
        time.sleep(2.5)
        rec.hold(1800)
        frame = driver.find_element(By.CSS_SELECTOR, "iframe[title='Report preview']")
        driver.switch_to.frame(frame)
        for _ in range(16):
            driver.execute_script("window.scrollBy(0, 110)")
            time.sleep(0.05)
            driver.switch_to.default_content()
            rec.snap(90)
            driver.switch_to.frame(frame)
        driver.switch_to.default_content()
        rec.hold(2200)

        OUT.parent.mkdir(parents=True, exist_ok=True)
        rec.save(OUT)
        print(f"Wrote {OUT.relative_to(ROOT)}: {len(rec.frames)} frames, {OUT.stat().st_size / 1e6:.1f} MB")
    finally:
        if driver is not None:
            driver.quit()
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
