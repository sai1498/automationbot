import requests
import json
import time
import os
from src.config import Config

class TelegramClient:
    def __init__(self):
        self.token = Config.TELEGRAM_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def _safe_request(self, method, url, **kwargs):
        """Helper to handle Telegram rate limits (429) with retries."""
        for attempt in range(5):
            try:
                response = requests.request(method, url, **kwargs)
                if response.status_code == 429:
                    retry_after = response.json().get("parameters", {}).get("retry_after", 5)
                    print(f"⚠️ Telegram Rate Limit (429). Retrying after {retry_after}s...")
                    time.sleep(retry_after)
                    continue
                
                # Special handling for 400 errors (like "message not modified")
                if response.status_code == 400:
                    error_data = response.json()
                    desc = error_data.get("description", "").lower()
                    if "message is not modified" in desc:
                        return error_data # Return instead of raising to avoid retry loop
                
                response.raise_for_status()
                return response.json()
            except requests.exceptions.HTTPError as e:
                if attempt == 4: raise
                # Don't retry on other 4xx errors unless they are 429
                if response.status_code < 500 and response.status_code != 429:
                    raise
                print(f"⚠️ HTTP Error: {e}. Retrying...")
                time.sleep(2 ** attempt)
        return None

    def send_message(self, text, parse_mode="Markdown", reply_markup=None, chat_id=None, token=None):
        url = self._build_url("sendMessage", token)
        payload = {
            "chat_id": chat_id or self.chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
            
        return self._safe_request("POST", url, json=payload)

    def _build_url(self, method_name, token=None):
        t = token or self.token
        return f"https://api.telegram.org/bot{t}/{method_name}"

    def edit_message_text(self, text, message_id, parse_mode="Markdown", reply_markup=None, chat_id=None, token=None):
        url = self._build_url("editMessageText", token)
        payload = {
            "chat_id": chat_id or self.chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        
        # We ignore errors where the message is already identical (Telegram throws a 400 for this)
        try:
            return self._safe_request("POST", url, json=payload)
        except Exception as e:
            if "message is not modified" in str(e).lower():
                return None
            raise

    def edit_message_reply_markup(self, message_id, reply_markup=None, chat_id=None, token=None):
        url = self._build_url("editMessageReplyMarkup", token)
        payload = {
            "chat_id": chat_id or self.chat_id,
            "message_id": message_id,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self._safe_request("POST", url, json=payload)

    def get_file(self, file_id, token=None):
        url = self._build_url("getFile", token)
        params = {"file_id": file_id}
        result = self._safe_request("GET", url, params=params)
        return result.get("result", {}) if result else {}

    def download_file(self, file_path, target_path, token=None):
        t = token or self.token
        url = f"https://api.telegram.org/file/bot{t}/{file_path}"
        response = requests.get(url) # Raw download, no _safe_request needed for binary
        response.raise_for_status()
        with open(target_path, "wb") as f:
            f.write(response.content)
        return target_path

    def send_media_group(self, paths, caption=None, is_local=True, token=None):
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
            
        payload = {
            "chat_id": self.chat_id,
            "media": json.dumps(media)
        }
        
        if is_local:
            result = self._safe_request("POST", url, data=payload, files=files)
            # Close files
            for f in files.values():
                f.close()
        else:
            result = self._safe_request("POST", url, json=payload)
            
        return result

    def send_to_publisher(self, text, reply_markup=None, publisher_token=None, chat_id=None):
        """Sends a private message to the publisher bot's current chat."""
        # This is a helper to use the publisher's own token for previews
        token = publisher_token or self.token
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id or self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        
        # We manually call requests here because it might use a DIFFERENT token than self.token
        # But let's wrap it in a local logic for safety
        for attempt in range(3):
             msg = requests.post(url, json=payload)
             if msg.status_code == 429:
                 time.sleep(5)
                 continue
             if msg.status_code != 200:
                 print(f"⚠️ Error in send_to_publisher: {msg.status_code} - {msg.text}")
             break

    def send_content_package(self, content_json, image_urls=None):
        """Formats and sends the entire JSON package to Telegram or only Community if specified."""
        
        is_community_only = content_json.get("is_community_only", False)

        if not is_community_only:
            # LinkedIn Post
            header = "💼 *LinkedIn Analysis*"
            self.send_message(f"{header}\n\n{content_json['linkedin_post']}")
            
            # Instagram/Post Hook
            header = "📸 *Instagram / Hook*"
            self.send_message(f"{header}\n\n{content_json['instagram_caption']}")
            
            # Carousel Slides & Images
            if image_urls:
                header = "📊 *Carousel Slides & Visuals*"
                # Check if image_urls are local paths (usually ending in .png or .jpg from temp_processing)
                is_local = any(isinstance(u, str) and ("temp_processing" in u or os.path.exists(u)) for u in image_urls)
                self.send_media_group(image_urls, caption=header, is_local=is_local)
            
            # Slides text (optional if images are enough, but let's keep it)
            slides_text = "\n".join([f"Slide {i+1}: {slide}" for i, slide in enumerate(content_json['carousel_slides'])])
            self.send_message(f"*Carousel Text Recap:*\n\n{slides_text}")

            # Image Prompts (Reference)
            header = "🎨 *Generation Prompts Used*"
            prompts_text = "\n\n".join([f"*Slide {i+1} Prompt:*\n`{prompt}`" for i, prompt in enumerate(content_json['image_prompts'])])
            self.send_message(f"{header}\n\n{prompts_text}")
        
        # Community is always sent
        header = "👥 *Community Discussion*"
        self.send_message(f"{header}\n\n{content_json['community_post']}")
    def send_community_post(self, content_json, token=None):
        """Sends ONLY the community discussion to the specified bot (usually the output bot)."""
        header = "👥 *Community Discussion*"
        return self.send_message(f"{header}\n\n{content_json['community_post']}", token=token)
        
        # If visuals are desired for the community too, we can add them here.
        # User said "only community information", so we'll stick to text for now.
        # If they ask for images later, we can re-add them.
