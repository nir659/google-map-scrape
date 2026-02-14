"""
Stealth HTTP client using curl_cffi for TLS-fingerprint evasion.

Wraps curl_cffi.requests with:
- Chrome TLS impersonation
- Header rotation
- Per-domain rate limiting
- Retry with exponential backoff
"""

import random
import time
import threading
from typing import Optional
from urllib.parse import urlparse

from curl_cffi import requests as cffi_requests
from loguru import logger

import src.config as cfg

# ── Rotating header pools ─────────────────────────────────────────────────

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:128.0) Gecko/20100101 Firefox/128.0",
]

_ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
    "en-AU,en;q=0.9",
    "en-US,en;q=0.9,fr;q=0.8",
    "en;q=0.9",
]


class StealthHTTPClient:
    """
    Thread-safe HTTP client that mimics a real Chrome browser.

    Handles TLS fingerprinting, rate limiting, and retries.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._domain_timestamps: dict[str, float] = {}

    @staticmethod
    def _random_headers(url: str) -> dict:
        """Generate randomised but realistic browser headers."""
        parsed = urlparse(url)
        return {
            "User-Agent": random.choice(_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": random.choice(_ACCEPT_LANGUAGES),
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": f"{parsed.scheme}://{parsed.netloc}/",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def _rate_limit(self, domain: str) -> None:
        """Enforce minimum delay between requests to the same domain."""
        with self._lock:
            last = self._domain_timestamps.get(domain, 0)
            elapsed = time.time() - last
            if elapsed < cfg.ENRICHER_SAME_DOMAIN_DELAY:
                wait = cfg.ENRICHER_SAME_DOMAIN_DELAY - elapsed
                time.sleep(wait)
            self._domain_timestamps[domain] = time.time()

    def get(self, url: str) -> Optional[str]:
        """
        Fetch *url* and return its HTML as a string.

        Returns None on unrecoverable failure (after retries).
        """
        domain = urlparse(url).netloc
        self._rate_limit(domain)

        last_exc: Exception | None = None

        for attempt in range(1, cfg.ENRICHER_MAX_RETRIES + 1):
            try:
                resp = cffi_requests.get(
                    url,
                    headers=self._random_headers(url),
                    timeout=cfg.ENRICHER_REQUEST_TIMEOUT,
                    impersonate="chrome120",
                    allow_redirects=True,
                )
                if resp.status_code == 200:
                    return resp.text
                if resp.status_code in (403, 401, 429, 503):
                    logger.debug(
                        "HTTP {} for {} (attempt {}/{})",
                        resp.status_code,
                        domain,
                        attempt,
                        cfg.ENRICHER_MAX_RETRIES,
                    )
                    # Don't retry auth/block errors -- skip immediately
                    return None
                # Other non-200
                logger.debug(
                    "HTTP {} for {} (attempt {}/{})",
                    resp.status_code,
                    domain,
                    attempt,
                    cfg.ENRICHER_MAX_RETRIES,
                )
            except Exception as exc:
                last_exc = exc
                logger.debug(
                    "Request failed for {} (attempt {}/{}): {}",
                    domain,
                    attempt,
                    cfg.ENRICHER_MAX_RETRIES,
                    exc,
                )

            # Exponential backoff before retry
            if attempt < cfg.ENRICHER_MAX_RETRIES:
                time.sleep(min(2 ** attempt, 8))

        if last_exc:
            logger.debug("All retries exhausted for {}: {}", domain, last_exc)
        return None
