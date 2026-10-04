"""HTML → PDF using headless Chrome's print-to-PDF (no WeasyPrint/GTK dependency on Windows)."""

from __future__ import annotations

import base64
import time
from pathlib import Path

from selenium.webdriver.common.print_page_options import PrintOptions

from app.scraper.driver import create_driver, safe_quit


def html_to_pdf(html_path: Path, pdf_path: Path, landscape: bool = False, wait: float = 1.5) -> Path:
    driver = create_driver(headless=True, driver_type="chrome", install_capture=False)
    try:
        driver.get(html_path.resolve().as_uri())
        time.sleep(wait)  # web fonts / images
        opts = PrintOptions()
        opts.background = True
        opts.orientation = "landscape" if landscape else "portrait"
        opts.margin_top = opts.margin_bottom = opts.margin_left = opts.margin_right = 0.0
        opts.page_width, opts.page_height = 21.0, 29.7  # A4 in cm
        pdf_path.write_bytes(base64.b64decode(driver.print_page(opts)))
        return pdf_path
    finally:
        safe_quit(driver)
