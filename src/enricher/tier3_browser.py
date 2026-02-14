"""
Tier 3: Headless browser rendering for JS-heavy websites.

Only triggered when Tiers 1 & 2 fail AND the raw HTML contains
indicators of a JS framework (React, Vue, Angular, Next.js, Nuxt).

Uses Playwright (already installed for Stage 1) to fully render the
page, then passes the rendered HTML to Tier 2's DOM parser.

Success rate boost: ~+10% (total ~95%).
"""

from typing import Optional

from loguru import logger

import src.config as cfg
from src.enricher.http_client import StealthHTTPClient
from src.enricher.tier2_dom import extract_email_tier2


def _is_js_heavy(html: str) -> bool:
    """Check if raw HTML suggests a JS framework that needs rendering."""
    html_lower = html.lower()
    return any(kw in html_lower for kw in cfg.JS_FRAMEWORK_KEYWORDS)


def extract_email_tier3(
    url: str,
    client: StealthHTTPClient,
    raw_html: Optional[str] = None,
) -> Optional[str]:
    """
    Tier 3: Render the page with Playwright, then parse rendered HTML.

    Parameters
    ----------
    url : str
        Website URL.
    client : StealthHTTPClient
        Shared HTTP client (passed to Tier 2 reuse).
    raw_html : str or None
        Pre-fetched raw HTML from Tier 1 -- used to check for JS indicators.

    Returns
    -------
    str or None
        Validated email address or None.
    """
    if not cfg.ENRICHER_ENABLE_TIER3:
        return None

    # Only fire if the page looks like it needs JS rendering
    if raw_html and not _is_js_heavy(raw_html):
        logger.debug("Tier 3 skipped (no JS framework detected): {}", url)
        return None

    logger.debug("Tier 3 rendering with Playwright: {}", url)

    try:
        from playwright.sync_api import sync_playwright
        from playwright_stealth import Stealth

        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        page = context.new_page()

        stealth = Stealth()
        stealth.apply_stealth_sync(page)

        page.goto(url, wait_until="domcontentloaded", timeout=15_000)
        # Give JS time to render
        page.wait_for_timeout(3000)

        rendered_html = page.content()

        browser.close()
        pw.stop()

        if rendered_html:
            # Re-run Tier 2 DOM extraction on the fully rendered HTML
            email = extract_email_tier2(url, client, html=rendered_html)
            if email:
                logger.debug("Tier 3 found email via rendered DOM: {}", email)
                return email

    except Exception as exc:
        logger.debug("Tier 3 Playwright failed for {}: {}", url, exc)

    return None
