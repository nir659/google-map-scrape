"""
Tier 1: Fast email extraction via regex on raw HTML.

No DOM parsing, no sub-page crawling -- just fetch and scan.
Success rate: ~60% on simple static sites.
"""

import re
from typing import Optional
from urllib.parse import unquote

from loguru import logger

from src.enricher.filters import clean_email
from src.enricher.http_client import StealthHTTPClient

# ── Email regex patterns (ordered by specificity) ─────────────────────────

# 1. mailto: links  (highest confidence)
_MAILTO_RE = re.compile(
    r"mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", re.IGNORECASE
)

# 2. Plain text email addresses
_PLAINTEXT_RE = re.compile(
    r"\b([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b"
)

# 3. URL-encoded emails (%40 = @)
_URLENCODED_RE = re.compile(
    r"\b([a-zA-Z0-9._%+\-]+%40[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b"
)


def extract_email_tier1(
    url: str,
    client: StealthHTTPClient,
) -> tuple[Optional[str], Optional[str]]:
    """
    Tier 1: Fetch the page and scan raw HTML with regex.

    Parameters
    ----------
    url : str
        Website URL to scan.
    client : StealthHTTPClient
        Shared HTTP client for TLS-safe requests.

    Returns
    -------
    tuple[str | None, str | None]
        (email, html) -- email if found, raw HTML for reuse by Tier 2.
    """
    html = client.get(url)
    if not html:
        return None, None

    # Try patterns in order of confidence
    for pattern, label in [
        (_MAILTO_RE, "mailto"),
        (_PLAINTEXT_RE, "plaintext"),
        (_URLENCODED_RE, "urlencoded"),
    ]:
        for match in pattern.finditer(html):
            raw = match.group(1)
            if label == "urlencoded":
                raw = unquote(raw)
            email = clean_email(raw)
            if email:
                logger.debug("Tier 1 ({}) found: {}", label, email)
                return email, html

    return None, html
