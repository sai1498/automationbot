"""
LinkedIn client — posts content via LinkedIn API.
Moved from src/linkedin_client.py with retry logic.
"""

import logging
import requests
from config.settings import Config
from core.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class LinkedInClient:
    """Publishes posts to LinkedIn via UGC API."""

    def __init__(self):
        self.access_token = Config.LINKEDIN_ACCESS_TOKEN
        self.person_id = Config.LINKEDIN_PERSON_ID
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }

    @retry_with_backoff(max_attempts=3, base_delay=2.0)
    def post_content(self, text: str, hashtags: list[str] = None):
        """Post text content to LinkedIn."""
        if not self.access_token:
            logger.info("LinkedIn access token missing — skipping")
            return

        url = "https://api.linkedin.com/v2/ugcPosts"
        full_text = f"{text}\n\n" + " ".join(hashtags or [])

        payload = {
            "author": f"urn:li:person:{self.person_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": full_text},
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }

        response = requests.post(url, headers=self.headers, json=payload, timeout=30)
        response.raise_for_status()
        logger.info("✅ Published to LinkedIn")
        return response.json()

    def publish(self, content_json: dict):
        """Publish from content JSON (used by orchestrator)."""
        hashtags = content_json.get("trending_hashtags", [])
        return self.post_content(content_json.get("linkedin_post", ""), hashtags)
