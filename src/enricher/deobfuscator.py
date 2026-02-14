"""
Cloudflare email de-obfuscation.

Cloudflare's "Email Address Obfuscation" feature replaces email addresses
with a <span data-cfemail="HEX_STRING"> or an <a> pointing to
/cdn-cgi/l/email-protection#HEX_STRING.

The hex string is a simple XOR cipher: the first byte is the key, and each
subsequent byte-pair is XOR'd with it to reveal the original character.
"""

from typing import Optional

from loguru import logger


def decode_cloudflare_email(encoded: str) -> Optional[str]:
    """
    Decode a Cloudflare-obfuscated email hex string.

    Parameters
    ----------
    encoded : str
        Hex string from ``data-cfemail`` attribute or URL fragment.
        Example: ``"543931193c3b2a3d147339353d7a3739"``

    Returns
    -------
    str or None
        Decoded email address, or None if decoding fails.
    """
    try:
        encoded = encoded.strip()
        if len(encoded) < 4 or len(encoded) % 2 != 0:
            return None

        key = int(encoded[:2], 16)
        result = ""
        for i in range(2, len(encoded), 2):
            result += chr(int(encoded[i : i + 2], 16) ^ key)

        # Sanity check: must look like an email
        if "@" in result and "." in result.split("@")[-1]:
            logger.debug("Cloudflare decoded: {} -> {}", encoded[:12] + "...", result)
            return result

        return None
    except (ValueError, IndexError) as exc:
        logger.debug("Cloudflare decode failed for '{}': {}", encoded[:20], exc)
        return None
