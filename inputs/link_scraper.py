"""
Web page scraper with URL safety validation.
Moved from src/link_scraper.py with SSRF protection.
"""

import logging
import requests
from bs4 import BeautifulSoup
from security.auth import sanitize_url
from core.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class LinkScraper:
    """Scrapes text content from URLs with security validation."""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    MAX_CONTENT_LENGTH = 4000  # Chars to return (avoid token limits)

    @retry_with_backoff(max_attempts=2, base_delay=1.0)
    def scrape(self, url: str) -> str:
        """Fetch and extract main text content from a URL."""
        # Security: validate URL first
        is_safe, reason = sanitize_url(url)
        if not is_safe:
            logger.warning(f"🛑 Blocked URL: {url} — {reason}")
            return f"⚠️ URL blocked: {reason}"

        try:
            response = requests.get(url, headers=self.HEADERS, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script and style elements
            for tag in soup(["script", "style"]):
                tag.decompose()

            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = "\n".join(chunk for chunk in chunks if chunk)

            return text[:self.MAX_CONTENT_LENGTH]
        except Exception as e:
            logger.error(f"Scraping error for {url}: {e}")
            return f"Error fetching content from {url}."
