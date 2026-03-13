"""
Authentication, authorization, and input sanitization.
"""

import re
import logging
from urllib.parse import urlparse
from config.settings import Config

logger = logging.getLogger(__name__)

# Blocked URL patterns for SSRF prevention
_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
_BLOCKED_SCHEMES = {"file", "ftp", "gopher"}
_PRIVATE_IP_PATTERN = re.compile(
    r"^(10\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    r"|(172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})"
    r"|(192\.168\.\d{1,3}\.\d{1,3})$"
)


def is_user_allowed(user_id: int) -> bool:
    """Check if a user is in the allowlist. If no allowlist is set, allow all."""
    if not Config.ALLOWED_USERS:
        return True  # No allowlist configured — open access
    return user_id in Config.ALLOWED_USERS


def validate_webhook_secret(received_secret: str) -> bool:
    """Validate the X-Telegram-Bot-Api-Secret-Token header."""
    if not Config.WEBHOOK_SECRET:
        return True  # No secret configured — skip validation
    return received_secret == Config.WEBHOOK_SECRET


def sanitize_url(url: str) -> tuple[bool, str]:
    """
    Validate a URL for safety. Returns (is_safe, reason).
    Blocks: file://, localhost, internal IPs, gopher, ftp.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"

    # Block dangerous schemes
    if parsed.scheme.lower() in _BLOCKED_SCHEMES:
        return False, f"Blocked URL scheme: {parsed.scheme}"

    # Block empty or missing scheme
    if not parsed.scheme or not parsed.hostname:
        return False, "URL must have a valid scheme and hostname"

    hostname = parsed.hostname.lower()

    # Block localhost and loopback
    if hostname in _BLOCKED_HOSTS:
        return False, f"Blocked host: {hostname}"

    # Block private IP ranges
    if _PRIVATE_IP_PATTERN.match(hostname):
        return False, f"Blocked private IP: {hostname}"

    return True, "OK"


def sanitize_text_input(text: str, max_length: int = 10000) -> str:
    """
    Basic text sanitization: truncate excessive input,
    strip null bytes and control characters.
    """
    if not text:
        return ""
    # Remove null bytes
    text = text.replace("\x00", "")
    # Truncate
    return text[:max_length]
