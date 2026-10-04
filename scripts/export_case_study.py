"""Export docs/case-study/case-study.html to PDF and 1600×1200 PNG slides (headless Chrome).

    python scripts/export_case_study.py

Writes to docs/case-study/export/:
    case-study.pdf            all slides, one per page
    slide-01.png … slide-09.png
    upwork-thumbnail.png      the cover slide
"""

from __future__ import annotations

import base64
import shutil
import time
from pathlib import Path

from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "case-study" / "case-study.html"
OUT = ROOT / "docs" / "case-study" / "export"
SIZE = (1600, 1200)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1600,1500")
    opts.add_argument("--force-device-scale-factor=1")
    opts.add_argument("--hide-scrollbars")
    driver = webdriver.Chrome(options=opts)
    try:
        driver.get(SRC.resolve().as_uri())
        end = time.time() + 10  # web fonts + images
        while time.time() < end and not driver.execute_script(
            "return document.fonts.status === 'loaded' && [...document.images].every(i => i.complete)"
        ):
            time.sleep(0.2)
        time.sleep(0.5)

        slides = driver.find_elements(By.CSS_SELECTOR, "section.slide")
        for i, slide in enumerate(slides, 1):
            driver.execute_script("arguments[0].scrollIntoView({block: 'start'})", slide)
            time.sleep(0.15)
            path = OUT / f"slide-{i:02d}.png"
            slide.screenshot(str(path))
            with Image.open(path) as img:
                if img.size != SIZE:  # e.g. a HiDPI override; normalise for Upwork
                    img.resize(SIZE, Image.LANCZOS).save(path)
            print(f"  {path.relative_to(ROOT)}")
        shutil.copyfile(OUT / "slide-01.png", OUT / "upwork-thumbnail.png")

        pdf = driver.execute_cdp_cmd(
            "Page.printToPDF",
            {
                "printBackground": True,
                "preferCSSPageSize": True,
                "marginTop": 0,
                "marginBottom": 0,
                "marginLeft": 0,
                "marginRight": 0,
            },
        )
        (OUT / "case-study.pdf").write_bytes(base64.b64decode(pdf["data"]))
        print(f"  {(OUT / 'case-study.pdf').relative_to(ROOT)} ({len(slides)} slides)")
    finally:
        driver.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
