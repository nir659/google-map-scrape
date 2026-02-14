"""
Browser factory -- launches Playwright Chromium with stealth injection.
"""

import time
import urllib.parse

from loguru import logger
from playwright.sync_api import Page, sync_playwright, BrowserContext
from playwright_stealth import Stealth

import src.config as cfg


GOOGLE_MAPS_SEARCH_URL = "https://www.google.com/maps/search/{query}/"


def create_browser_context() -> tuple:
    """
    Launch a Chromium browser with stealth applied.

    Returns
    -------
    tuple
        (playwright_instance, browser, context, page)
        Caller is responsible for closing via ``close_browser()``.
    """
    pw = sync_playwright().start()

    browser = pw.chromium.launch(
        headless=cfg.HEADLESS,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    )

    context: BrowserContext = browser.new_context(
        viewport={
            "width": cfg.VIEWPORT_WIDTH,
            "height": cfg.VIEWPORT_HEIGHT,
        },
        locale=cfg.LOCALE,
        user_agent=cfg.USER_AGENT,
    )
    context.set_default_timeout(cfg.PAGE_LOAD_TIMEOUT)
    context.set_default_navigation_timeout(cfg.NAVIGATION_TIMEOUT)

    page: Page = context.new_page()

    # playwright-stealth v2 API
    stealth = Stealth()
    stealth.apply_stealth_sync(page)

    logger.info("Browser context created (headless={})", cfg.HEADLESS)
    return pw, browser, context, page


def search_maps(page: Page, query: str) -> None:
    """
    Navigate directly to Google Maps search results for *query*.

    This is far more reliable than loading the homepage and typing into
    the search box, because it avoids cookie banners, regional overlays,
    and timing issues with the search input becoming interactive.
    """
    encoded = urllib.parse.quote(query)
    url = GOOGLE_MAPS_SEARCH_URL.format(query=encoded)

    # Don't use "networkidle" -- Google Maps streams map tiles and
    # analytics indefinitely, so networkidle never fires.  Load the DOM
    # first, then wait for the specific element we actually need.
    page.goto(url, wait_until="domcontentloaded")
    logger.info("Navigated to search results for '{}'", query)

    # Dismiss cookie consent banner if present
    try:
        accept_btn = page.locator(cfg.ACCEPT_COOKIES)
        if accept_btn.is_visible(timeout=3000):
            accept_btn.click()
            logger.info("Cookie consent dismissed")
            time.sleep(1)
    except Exception:
        pass  # Banner not shown -- continue

    # Wait for the results sidebar -- this is the real readiness signal
    page.locator(cfg.SIDEBAR_FEED).wait_for(
        state="attached", timeout=cfg.PAGE_LOAD_TIMEOUT
    )
    # Let the first batch of cards render
    page.locator(cfg.RESULT_CARD).first.wait_for(
        state="attached", timeout=cfg.PAGE_LOAD_TIMEOUT
    )
    time.sleep(cfg.SEARCH_WAIT)
    logger.info("Results feed loaded")


def close_browser(pw, browser) -> None:
    """Gracefully shut down the browser and Playwright."""
    try:
        browser.close()
    except Exception:
        pass
    try:
        pw.stop()
    except Exception:
        pass
    logger.info("Browser closed")
