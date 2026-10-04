"""Chrome WebDriver factory: headless / visible, standard Selenium or undetected-chromedriver.

Selenium Manager (bundled with Selenium 4.6+) downloads a matching chromedriver automatically,
so the only prerequisite is an installed Google Chrome.
"""

from __future__ import annotations

import logging
from typing import Any

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from app.core.config import env, get_settings

log = logging.getLogger(__name__)

# Collects the Ad Library's own /api/graphql/ pagination responses as the page receives them.
# Injected before any page script runs; only responses that contain ad results are kept.
XHR_CAPTURE_JS = r"""
(() => {
  if (window.__adspyInstalled) return;
  window.__adspyInstalled = true;
  window.__adspy = [];
  const keep = (url, body) => {
    try {
      if (String(url).includes('graphql') && body && body.includes('ad_archive_id')) {
        window.__adspy.push(body);
      }
    } catch (e) {}
  };
  const open = XMLHttpRequest.prototype.open;
  const send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (m, u) { this.__adspyUrl = u; return open.apply(this, arguments); };
  XMLHttpRequest.prototype.send = function () {
    this.addEventListener('load', () => {
      try { if (this.responseType === '' || this.responseType === 'text') keep(this.__adspyUrl, this.responseText); } catch (e) {}
    });
    return send.apply(this, arguments);
  };
  const origFetch = window.fetch;
  if (origFetch) {
    window.fetch = function (input, init) {
      return origFetch.apply(this, arguments).then((resp) => {
        try {
          const url = typeof input === 'string' ? input : (input && input.url);
          if (String(url).includes('graphql')) resp.clone().text().then((t) => keep(url, t)).catch(() => {});
        } catch (e) {}
        return resp;
      });
    };
  }
})();
"""


def _options(headless: bool, cfg: dict[str, Any]) -> Options:
    opts = Options()
    width, height = cfg.get("window_size", [1440, 1000])
    lang = cfg.get("language", "en-US")
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument(f"--window-size={width},{height}")
    opts.add_argument(f"--lang={lang}")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument("--mute-audio")
    opts.add_experimental_option("prefs", {"intl.accept_languages": lang})
    binary = env("CHROME_BINARY")
    if binary:
        opts.binary_location = binary
    return opts


def create_driver(
    headless: bool | None = None, driver_type: str | None = None, install_capture: bool = True
) -> webdriver.Chrome:
    cfg = get_settings().get("scraping", {})
    headless = cfg.get("headless", True) if headless is None else headless
    driver_type = (driver_type or cfg.get("driver", "chrome")).lower()

    if driver_type == "undetected":
        try:
            import undetected_chromedriver as uc  # type: ignore[import-not-found]

            opts = uc.ChromeOptions()
            for arg in _options(headless, cfg).arguments:
                if arg != "--disable-blink-features=AutomationControlled":
                    opts.add_argument(arg)
            driver = uc.Chrome(options=opts, headless=headless, use_subprocess=True)
            log.info("Started undetected-chromedriver (headless=%s)", headless)
        except ImportError:
            log.warning(
                "driver=undetected but undetected-chromedriver is not installed; "
                "falling back to standard Chrome. Install with: pip install undetected-chromedriver"
            )
            driver_type = "chrome"

    if driver_type != "undetected":
        opts = _options(headless, cfg)
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        driver = webdriver.Chrome(options=opts)
        log.info("Started Chrome %s (headless=%s)", driver.capabilities.get("browserVersion"), headless)
        if headless:
            # Headless Chrome advertises itself in the UA; present the regular desktop string.
            ua = driver.execute_script("return navigator.userAgent").replace("HeadlessChrome", "Chrome")
            driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": ua})

    driver.set_page_load_timeout(int(cfg.get("page_load_timeout", 45)))
    if install_capture:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": XHR_CAPTURE_JS})
    return driver


def safe_quit(driver: Any) -> None:
    try:
        driver.quit()
    except Exception:  # noqa: BLE001 — browser may already be gone
        log.debug("driver.quit() failed", exc_info=True)
