"""
Data extraction -- turns Playwright locators into Pydantic models.

Extracts all visible info from each Google Maps sidebar card:
name, link, phone, website, address, rating, reviews, category.
"""

import re
from typing import List, Optional, Tuple

from loguru import logger
from playwright.sync_api import Locator, Page

import src.config as cfg
from src.models.business import Business

# ── Regex patterns ────────────────────────────────────────────────────────────

# Phone: (07) 4122 1226 | 0438 253 005 | (212) 555-1234 | +61 7 4122 1226
_PHONE_RE = re.compile(
    r"(\+?\d{1,3}[\s.-]?)?"          # optional country code
    r"(\(?\d{2,4}\)?[\s.-]?)"         # area code
    r"(\d{3,4}[\s.-]?\d{3,4})"        # subscriber number
)

# Rating line: "4.6(23)" or "4.6 (23)" or just "4.6"
_RATING_RE = re.compile(r"(\d\.\d)\s*(?:\((\d[\d,]*)\))?")


# ── Text-parsing helpers ─────────────────────────────────────────────────────

def _extract_phone(text: str) -> Optional[str]:
    """Find the first phone-number-like string in *text*."""
    for line in text.splitlines():
        line = line.strip()
        match = _PHONE_RE.search(line)
        if match:
            candidate = match.group(0).strip()
            # Must have at least 8 digits to be a real phone number
            digits = re.sub(r"\D", "", candidate)
            if len(digits) >= 8:
                return candidate
    return None


def _extract_rating_reviews(text: str) -> Tuple[Optional[float], Optional[int]]:
    """Pull star rating and review count from card text."""
    match = _RATING_RE.search(text)
    if not match:
        return None, None

    rating = float(match.group(1))
    if not (1.0 <= rating <= 5.0):
        return None, None

    reviews = None
    if match.group(2):
        reviews = int(match.group(2).replace(",", ""))

    return rating, reviews


def _extract_category_and_address(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Google Maps usually shows a line like:
        "Plumber · 89 Tooley St"
    Split on the middle-dot separator to get category and address.
    """
    for line in text.splitlines():
        line = line.strip()
        if "\u00b7" in line:                    # unicode middle dot ·
            parts = [p.strip() for p in line.split("\u00b7")]
            if len(parts) >= 2:
                return parts[0], parts[1]
            if len(parts) == 1:
                return parts[0], None
    return None, None


def _get_website_url(container: Locator) -> Optional[str]:
    """Look for the 'Website' action button inside the card container."""
    try:
        link = container.locator(cfg.WEBSITE_LINK)
        if link.count():
            return link.first.get_attribute("href")
    except Exception:
        pass
    return None


# ── Main extraction ──────────────────────────────────────────────────────────

def extract_listings(page: Page, query_name: str) -> List[Business]:
    """
    Parse every result card visible in the sidebar, extracting all
    available data (name, link, phone, website, address, rating,
    reviews, category).

    Parameters
    ----------
    page : Page
        Playwright page after scrolling is complete.
    query_name : str
        Label for the originating query (stored on each record).

    Returns
    -------
    List[Business]
        De-duplicated list of scraped entries.
    """
    cards = page.locator(cfg.RESULT_CARD).all()
    logger.info("Parsing {} result cards ...", len(cards))

    seen_links: set = set()
    results: List[Business] = []

    for card in cards:
        try:
            name = card.get_attribute("aria-label") or ""
            link = card.get_attribute("href") or ""

            if not name or not link:
                continue
            if link in seen_links:
                continue
            seen_links.add(link)

            # Navigate to the card container (parent holds all card content)
            container = card.locator("xpath=..")

            # Get full visible text from the card container
            try:
                card_text = container.inner_text(timeout=2000)
            except Exception:
                card_text = ""

            # Parse structured data from text
            phone = _extract_phone(card_text)
            rating, reviews = _extract_rating_reviews(card_text)
            category, address = _extract_category_and_address(card_text)

            # Website link from action button
            website = _get_website_url(container)

            results.append(
                Business(
                    name=name.strip(),
                    link=link.strip(),
                    phone=phone,
                    website=website,
                    address=address,
                    rating=rating,
                    reviews=reviews,
                    category=category,
                    query_source=query_name,
                )
            )
        except Exception as exc:
            logger.warning("Failed to parse a card: {}", exc)
            continue

    logger.info(
        "Extracted {} unique listings (from {} cards)",
        len(results),
        len(cards),
    )
    return results
