"""HTML → PDF using headless Chrome's print engine (no WeasyPrint/GTK dependency on Windows).

Uses the DevTools `Page.printToPDF` command with `preferCSSPageSize`, so the template's
`@page` rules (A4, margins, a margin-free cover and "Page X of Y" footers) are honored.
"""

from __future__ import annotations

import base64
import logging
import time
from pathlib import Path

from selenium.webdriver.common.print_page_options import PrintOptions

from app.scraper.driver import create_driver, safe_quit

log = logging.getLogger(__name__)


def _wait_for_fonts(driver, timeout: float = 6.0) -> None:  # noqa: ANN001
    end = time.time() + timeout
    while time.time() < end:
        try:
            if driver.execute_script("return document.fonts ? document.fonts.status === 'loaded' : true"):
                return
        except Exception:  # noqa: BLE001
            return
        time.sleep(0.2)


def html_to_pdf(html_path: Path, pdf_path: Path, landscape: bool = False, wait: float = 0.8) -> Path:
    driver = create_driver(headless=True, driver_type="chrome", install_capture=False)
    try:
        driver.get(html_path.resolve().as_uri())
        _wait_for_fonts(driver)
        time.sleep(wait)  # images decode
        try:
            result = driver.execute_cdp_cmd(
                "Page.printToPDF",
                {
                    "printBackground": True,
                    "preferCSSPageSize": True,
                    "landscape": landscape,
                    "paperWidth": 8.27,  # A4 fallback when the page sets no @page size
                    "paperHeight": 11.69,
                    "marginTop": 0,
                    "marginBottom": 0,
                    "marginLeft": 0,
                    "marginRight": 0,
                },
            )
            data = result["data"]
        except Exception as exc:  # noqa: BLE001 — e.g. a non-Chromium driver
            log.info("CDP printToPDF unavailable (%s); using WebDriver print", exc)
            opts = PrintOptions()
            opts.background = True
            opts.orientation = "landscape" if landscape else "portrait"
            opts.margin_top = opts.margin_bottom = opts.margin_left = opts.margin_right = 0.0
            opts.page_width, opts.page_height = 21.0, 29.7
            data = driver.print_page(opts)
        pdf_path.write_bytes(base64.b64decode(data))
        return pdf_path
    finally:
        safe_quit(driver)
