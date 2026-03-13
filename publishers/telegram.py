"""
Telegram client — handles all Telegram API interactions.
Moved from src/telegram_client.py with retry logic and structured logging.
"""

import os
import json
import time
import logging

import requests
from config.settings import Config

logger = logging.getLogger(__name__)


class TelegramClient:
    """Handles all Telegram Bot API interactions with automatic rate-limit handling."""

    def __init__(self):
        self.token = Config.TELEGRAM_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def _build_url(self, method_name: str, token: str = None) -> str:
        t = token or self.token
        return f"https://api.telegram.org/bot{t}/{method_name}"

    def _safe_request(self, method: str, url: str, **kwargs):
        """HTTP request with Telegram rate-limit (429) handling and retries."""
        for attempt in range(5):
            try:
                response = requests.request(method, url, **kwargs)

                if response.status_code == 429:
                    retry_after = response.json().get("parameters", {}).get("retry_after", 5)
                    logger.warning(f"⚠️ Telegram 429 — retrying after {retry_after}s")
                    time.sleep(retry_after)
                    continue

                if response.status_code == 400:
                    error_data = response.json()
                    desc = error_data.get("description", "").lower()
                    if "message is not modified" in desc:
                        return error_data

                response.raise_for_status()
                return response.json()

            except requests.exceptions.HTTPError as e:
                if attempt == 4:
                    raise
                if response.status_code < 500 and response.status_code != 429:
                    raise
                logger.warning(f"⚠️ HTTP Error: {e}. Retry {attempt + 1}/5")
                time.sleep(2 ** attempt)
        return None

    def send_message(self, text: str, parse_mode: str = "Markdown",
                     reply_markup=None, chat_id=None, token=None):
        url = self._build_url("sendMessage", token)
        payload = {
            "chat_id": chat_id or self.chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self._safe_request("POST", url, json=payload)

    def edit_message_text(self, text: str, message_id: int, parse_mode: str = "Markdown",
                          reply_markup=None, chat_id=None, token=None):
        url = self._build_url("editMessageText", token)
        payload = {
            "chat_id": chat_id or self.chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            return self._safe_request("POST", url, json=payload)
        except Exception as e:
            if "message is not modified" in str(e).lower():
                return None
            raise

    def edit_message_reply_markup(self, message_id: int, reply_markup=None,
                                  chat_id=None, token=None):
        url = self._build_url("editMessageReplyMarkup", token)
        payload = {"chat_id": chat_id or self.chat_id, "message_id": message_id}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self._safe_request("POST", url, json=payload)

    def get_file(self, file_id: str, token=None) -> dict:
        url = self._build_url("getFile", token)
        result = self._safe_request("GET", url, params={"file_id": file_id})
        return result.get("result", {}) if result else {}

    def download_file(self, file_path: str, target_path: str, token=None) -> str:
        t = token or self.token
        url = f"https://api.telegram.org/file/bot{t}/{file_path}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        with open(target_path, "wb") as f:
            f.write(response.content)
        return target_path

    def send_media_group(self, paths: list, caption: str = None,
                         is_local: bool = True, token=None):
        url = self._build_url("sendMediaGroup", token)
        media = []
        files = {}

        for i, path in enumerate(paths):
            attach_name = f"photo_{i}"
            media_item = {
                "type": "photo",
                "media": f"attach://{attach_name}" if is_local else path
            }
            if i == 0 and caption:
                media_item["caption"] = caption
                media_item["parse_mode"] = "Markdown"
            media.append(media_item)

            if is_local:
                files[attach_name] = open(path, "rb")

        payload = {"chat_id": self.chat_id, "media": json.dumps(media)}

        try:
            if is_local:
                result = self._safe_request("POST", url, data=payload, files=files)
            else:
                result = self._safe_request("POST", url, json=payload)
            return result
        finally:
            for f in files.values():
                f.close()

    def send_to_publisher(self, text: str, reply_markup=None,
                          publisher_token=None, chat_id=None):
        """Send a message using a specific bot token (for publisher previews)."""
        token = publisher_token or self.token
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id or self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        for attempt in range(3):
            msg = requests.post(url, json=payload, timeout=30)
            if msg.status_code == 429:
                time.sleep(5)
                continue
            if msg.status_code != 200:
                logger.warning(f"⚠️ send_to_publisher: {msg.status_code} - {msg.text[:200]}")
            break

    def send_content_package(self, content_json: dict, image_urls=None):
        """Format and send the entire content package to Telegram."""
        is_community_only = content_json.get("is_community_only", False)

        if not is_community_only:
            self.send_message(f"💼 *LinkedIn Analysis*\n\n{content_json['linkedin_post']}")
            self.send_message(f"📸 *Instagram / Hook*\n\n{content_json['instagram_caption']}")

            if image_urls:
                is_local = any(isinstance(u, str) and os.path.exists(u) for u in image_urls)
                self.send_media_group(image_urls, caption="📊 *Carousel Slides & Visuals*", is_local=is_local)

            slides_text = "\n".join(
                f"Slide {i+1}: {slide}" for i, slide in enumerate(content_json["carousel_slides"])
            )
            self.send_message(f"*Carousel Text Recap:*\n\n{slides_text}")

            prompts_text = "\n\n".join(
                f"*Slide {i+1} Prompt:*\n`{prompt}`"
                for i, prompt in enumerate(content_json["image_prompts"])
            )
            self.send_message(f"🎨 *Generation Prompts Used*\n\n{prompts_text}")

        self.send_message(f"👥 *Community Discussion*\n\n{content_json['community_post']}")

    def send_community_post(self, content_json: dict, token=None):
        """Send ONLY the community discussion."""
        return self.send_message(
            f"👥 *Community Discussion*\n\n{content_json['community_post']}",
            token=token
        )
