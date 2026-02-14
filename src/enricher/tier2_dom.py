"""
Tier 2: DOM-based email extraction with BeautifulSoup.

- Parses <a href="mailto:..."> attributes
- Decodes Cloudflare-obfuscated emails (data-cfemail XOR)
- Follows /contact or /about sub-pages (max depth: 1)

Success rate: ~85% (covers obfuscated emails and contact pages).
"""

import re
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from loguru import logger

from src.enricher.deobfuscator import decode_cloudflare_email
from src.enricher.filters import clean_email
from src.enricher.http_client import StealthHTTPClient

# ── Contact-page link patterns ────────────────────────────────────────────

_CONTACT_RE = re.compile(r"(contact|about|reach-us|get-in-touch)", re.IGNORECASE)


def _extract_from_soup(soup: BeautifulSoup) -> Optional[str]:
    """
    Scan a parsed DOM tree for email addresses.

    Checks (in order):
    1. <a href="mailto:..."> links
    2. Cloudflare-obfuscated <span data-cfemail="..."> / <a data-cfemail="...">
    3. Cloudflare /cdn-cgi/l/email-protection#HEX href links
    """
    # 1. mailto: attributes
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if href.lower().startswith("mailto:"):
            raw = href[7:].split("?")[0]  # strip ?subject=... params
            email = clean_email(raw)
            if email:
                logger.debug("Tier 2 (mailto attr) found: {}", email)
                return email

    # 2. data-cfemail spans and links
    for tag in soup.find_all(attrs={"data-cfemail": True}):
        encoded = tag["data-cfemail"]
        decoded = decode_cloudflare_email(encoded)
        if decoded:
            email = clean_email(decoded)
            if email:
                logger.debug("Tier 2 (cloudflare decode) found: {}", email)
                return email

    # 3. /cdn-cgi/l/email-protection#HEX links
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if "/cdn-cgi/l/email-protection#" in href:
            hex_part = href.split("#", 1)[1]
            decoded = decode_cloudflare_email(hex_part)
            if decoded:
                email = clean_email(decoded)
                if email:
                    logger.debug("Tier 2 (cf protection link) found: {}", email)
                    return email

    return None


def _find_contact_urls(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Find up to 3 internal links that look like contact/about pages."""
    base_domain = urlparse(base_url).netloc
    candidates: list[str] = []

    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        text = tag.get_text(strip=True).lower()

        # Match by link text or href path
        if _CONTACT_RE.search(text) or _CONTACT_RE.search(href):
            full_url = urljoin(base_url, href)
            # Only follow same-domain links
            if urlparse(full_url).netloc == base_domain:
                if full_url not in candidates:
                    candidates.append(full_url)
                    if len(candidates) >= 3:
                        break

    # Prefer /contact over /about
    candidates.sort(key=lambda u: (0 if "contact" in u.lower() else 1))
    return candidates


def extract_email_tier2(
    url: str,
    client: StealthHTTPClient,
    html: Optional[str] = None,
) -> Optional[str]:
    """
    Tier 2: Parse HTML DOM for emails, then crawl contact page if needed.

    Parameters
    ----------
    url : str
        Website URL (used as base for relative links).
    client : StealthHTTPClient
        Shared HTTP client.
    html : str or None
        Pre-fetched HTML from Tier 1 (avoids double-fetch).

    Returns
    -------
    str or None
        Validated email address or None.
    """
    if not html:
        html = client.get(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "lxml")

    # Try homepage DOM first
    email = _extract_from_soup(soup)
    if email:
        return email

    # Crawl contact/about sub-pages (depth 1)
    contact_urls = _find_contact_urls(soup, url)
    for contact_url in contact_urls:
        logger.debug("Tier 2 following contact page: {}", contact_url)
        contact_html = client.get(contact_url)
        if not contact_html:
            continue
        contact_soup = BeautifulSoup(contact_html, "lxml")
        email = _extract_from_soup(contact_soup)
        if email:
            return email

    return None
