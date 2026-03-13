"""
Instagram client — publishes photos via Graph API.
Moved from src/instagram_client.py with retry logic.
"""

import logging
import requests
from config.settings import Config
from core.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class InstagramClient:
    """Publishes content to Instagram via Facebook Graph API."""

    def __init__(self):
        self.business_account_id = Config.INSTAGRAM_BUSINESS_ACCOUNT_ID
        self.access_token = Config.INSTAGRAM_ACCESS_TOKEN

    @retry_with_backoff(max_attempts=3, base_delay=2.0)
    def publish_photo(self, image_url: str, caption: str, hashtags: list[str] = None):
        """Publish a photo to Instagram."""
        if not self.access_token:
            logger.info("Instagram access token missing — skipping")
            return

        # 1. Create media container
        container_url = f"https://graph.facebook.com/v18.0/{self.business_account_id}/media"
        full_caption = f"{caption}\n\n" + " ".join(hashtags or [])

        payload = {
            "image_url": image_url,
            "caption": full_caption,
            "access_token": self.access_token
        }

        res = requests.post(container_url, data=payload, timeout=30)
        res.raise_for_status()
        creation_id = res.json().get("id")

        # 2. Publish the container
        publish_url = f"https://graph.facebook.com/v18.0/{self.business_account_id}/media_publish"
        publish_payload = {
            "creation_id": creation_id,
            "access_token": self.access_token
        }

        final_res = requests.post(publish_url, data=publish_payload, timeout=30)
        final_res.raise_for_status()
        logger.info("✅ Published to Instagram")
        return final_res.json()
