"""
Email validation and junk filtering.

Catches fake, generic, and image-extension emails before they pollute output.
"""

import re
from typing import Optional

from loguru import logger

# ── Blocklist: domains that never yield useful contact emails ─────────────

BLOCKLIST_DOMAINS = frozenset(
    {
        "example.com",
        "test.com",
        "localhost",
        "wix.com",
        "weebly.com",
        "squarespace.com",
        "godaddy.com",
        "sentry.io",
        "google-analytics.com",
        "googleusercontent.com",
        "googleapis.com",
        "facebook.com",
        "twitter.com",
        "instagram.com",
        "youtube.com",
        "linkedin.com",
        "schema.org",
        "w3.org",
        "gravatar.com",
        "wordpress.org",
        "wp.com",
    }
)

# ── Blocklist: local-part prefixes that indicate non-personal addresses ───

BLOCKLIST_LOCAL_PREFIXES = (
    "noreply",
    "no-reply",
    "donotreply",
    "do-not-reply",
    "mailer-daemon",
    "postmaster",
    "hostmaster",
    "webmaster",
    "abuse",
    "root",
    "nobody",
    "image",
    "img",
    "icon",
    "logo",
    "banner",
    "placeholder",
)

# ── File extension patterns that sometimes sneak into regex matches ───────

_FILE_EXT_RE = re.compile(
    r"\.(png|jpg|jpeg|gif|svg|webp|ico|bmp|tiff|pdf|css|js|woff|woff2|ttf|eot)$",
    re.IGNORECASE,
)

# ── Core email format regex ──────────────────────────────────────────────

_EMAIL_FORMAT_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


def is_valid_email(email: Optional[str]) -> bool:
    """
    Return True only if *email* passes format, domain, and junk checks.
    """
    if not email:
        return False

    email = email.strip().lower()

    # Basic format
    if not _EMAIL_FORMAT_RE.match(email):
        return False

    # File extension masquerading as email
    if _FILE_EXT_RE.search(email):
        return False

    # Domain blocklist
    domain = email.split("@", 1)[1]
    if domain in BLOCKLIST_DOMAINS:
        return False
    # Sub-domain check (e.g. mail.example.com)
    for blocked in BLOCKLIST_DOMAINS:
        if domain.endswith("." + blocked):
            return False

    # Local-part prefix blocklist
    local = email.split("@", 1)[0]
    for prefix in BLOCKLIST_LOCAL_PREFIXES:
        if local == prefix or local.startswith(prefix + "."):
            return False

    return True


def clean_email(raw: str) -> Optional[str]:
    """
    Normalise and validate a raw email string.

    Returns the cleaned email or None if invalid.
    """
    if not raw:
        return None
    cleaned = raw.strip().lower().rstrip(".")
    # Remove trailing query strings or anchors that sometimes stick
    cleaned = cleaned.split("?")[0].split("#")[0]
    if is_valid_email(cleaned):
        return cleaned
    return None
