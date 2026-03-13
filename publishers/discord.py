"""
Discord client — sends content via webhook.
Moved from src/discord_client.py with retry logic.
"""

import logging
import requests
from config.settings import Config
from core.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class DiscordClient:
    """Sends formatted content to Discord via webhook."""

    def __init__(self):
        self.webhook_url = Config.DISCORD_WEBHOOK_URL

    @retry_with_backoff(max_attempts=3, base_delay=2.0)
    def send_message(self, content: str):
        if not self.webhook_url:
            logger.info("Discord webhook not configured — skipping")
            return
        payload = {"content": content}
        response = requests.post(self.webhook_url, json=payload, timeout=15)
        response.raise_for_status()
        return response

    def send_content_package(self, content_json: dict):
        """Format and send content to Discord."""
        is_community_only = content_json.get("is_community_only", False)

        if is_community_only:
            self.send_message(f"**👥 Community Discussion**\n\n{content_json['community_post']}")
        else:
            analysis = (
                f"**💼 LinkedIn Analysis**\n{content_json['linkedin_post']}\n\n"
                f"**📸 Instagram Hook**\n{content_json['instagram_caption']}\n\n"
                f"**👥 Community Discussion**\n{content_json['community_post']}"
            )
            self.send_message(analysis)

            slides = "**📊 Carousel Slides**\n" + "\n".join(
                f"Slide {i+1}: {slide}"
                for i, slide in enumerate(content_json["carousel_slides"])
            )
            self.send_message(slides)
