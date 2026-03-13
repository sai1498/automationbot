"""
Main orchestrator — coordinates input processing, content generation, and publishing.
Extracted from src/publisher_bot.py with database-backed state and security.
"""

import json
import re
import logging
from datetime import datetime, timezone

from config.settings import Config
from core.pipeline import ContentPipeline
from publishers.telegram import TelegramClient
from publishers.discord import DiscordClient
from publishers.linkedin import LinkedInClient
from publishers.instagram import InstagramClient
from inputs.transcriber import AudioTranscriber
from inputs.image_parser import ImageParser
from inputs.link_scraper import LinkScraper
from security.auth import is_user_allowed, sanitize_text_input
from security.rate_limit import rate_limiter
from database.models import get_session_factory
from task_queue.tasks import Task, TaskType
from task_queue.worker import task_worker

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Main bot orchestrator — handles message routing, content generation, review, and publishing.
    Uses database-backed sessions instead of in-memory state.
    """

    def __init__(self):
        self.listener_token = Config.TELEGRAM_TOKEN
        self.publisher_token = Config.PUBLISHER_BOT_TOKEN or Config.TELEGRAM_TOKEN

        # Core components
        self.pipeline = ContentPipeline()
        self.tg_client = TelegramClient()
        self.discord_client = DiscordClient()
        self.linkedin_client = LinkedInClient()
        self.instagram_client = InstagramClient()
        self.transcriber = AudioTranscriber()
        self.image_parser = ImageParser()
        self.link_scraper = LinkScraper()

        logger.info("✅ Orchestrator initialized")

    def process_message(self, message: dict):
        """Process an incoming Telegram message through the full pipeline."""
        chat_id = message.get("chat", {}).get("id")
        user_id = message.get("from", {}).get("id", chat_id)
        logger.info(f"📥 Message from chat_id={chat_id}, user_id={user_id}")

        # ─── Security Checks ────────────────────────────
        # 1. Chat ID check (legacy)
        if Config.TELEGRAM_CHAT_ID and str(chat_id) != str(Config.TELEGRAM_CHAT_ID):
            logger.warning(f"🛑 Blocked: chat_id={chat_id} != configured={Config.TELEGRAM_CHAT_ID}")
            return

        # 2. User allowlist
        if not is_user_allowed(user_id):
            logger.warning(f"🛑 Blocked: user_id={user_id} not in ALLOWED_USERS")
            self.tg_client.send_to_publisher(
                "🛑 *Access Denied.* You are not authorized to use this bot.",
                publisher_token=self.listener_token, chat_id=chat_id
            )
            return

        # 3. Rate limit
        allowed, remaining = rate_limiter.check(user_id)
        if not allowed:
            self.tg_client.send_to_publisher(
                "⏳ *Rate limit reached.* Please wait a moment before sending more requests.",
                publisher_token=self.listener_token, chat_id=chat_id
            )
            return

        # ─── Input Processing ────────────────────────────
        input_text = ""
        input_type = "text"

        if "voice" in message:
            input_type = "voice"
            logger.info("🎤 Processing voice note...")
            self.tg_client.send_to_publisher(
                "🎤 *Voice note detected. Transcribing...*",
                publisher_token=self.listener_token, chat_id=chat_id
            )
            file_info = self.tg_client.get_file(message["voice"]["file_id"], token=self.listener_token)
            local_path = self.tg_client.download_file(file_info["file_path"], "temp_voice.ogg", token=self.listener_token)
            input_text = self.transcriber.transcribe(local_path)
            self.tg_client.send_to_publisher(
                f'📝 *Transcribed:* "{input_text[:100]}..."',
                publisher_token=self.listener_token, chat_id=chat_id
            )

        elif "photo" in message:
            input_type = "photo"
            logger.info("📸 Processing photo...")
            self.tg_client.send_to_publisher(
                "🖼️ *Photo detected. Analyzing...*",
                publisher_token=self.listener_token, chat_id=chat_id
            )
            photo = message["photo"][-1]
            file_info = self.tg_client.get_file(photo["file_id"], token=self.listener_token)
            local_path = self.tg_client.download_file(file_info["file_path"], "temp_vision.jpg", token=self.listener_token)
            input_text = self.image_parser.analyze_image(local_path)
            self.tg_client.send_to_publisher(
                f'👁️ *Analysis:* "{input_text[:100]}..."',
                publisher_token=self.listener_token, chat_id=chat_id
            )

        elif "text" in message:
            input_text = message["text"]
            # Check for URLs
            urls = re.findall(
                r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
                input_text
            )
            if urls:
                input_type = "url"
                self.tg_client.send_to_publisher(
                    f"🔗 *URL detected. Scraping {urls[0]}...*",
                    publisher_token=self.listener_token, chat_id=chat_id
                )
                input_text = self.link_scraper.scrape(urls[0])

        if not input_text:
            return

        # Sanitize input
        input_text = sanitize_text_input(input_text)

        logger.info(f"🚀 Processing [{input_type}]: {input_text[:50]}...")
        self.tg_client.send_to_publisher(
            "⚙️ *Starting multi-platform processing flow...*",
            publisher_token=self.listener_token, chat_id=chat_id
        )

        try:
            # Run the content pipeline
            if not input_text.strip().upper().startswith("[COMMUNITY]"):
                self.tg_client.send_to_publisher(
                    "🎨 *Generating content and images...*",
                    publisher_token=self.listener_token, chat_id=chat_id
                )

            # Define the task callback
            def pipeline_callback(task):
                if task.status == "completed":
                    res = task.result
                    # Save session (DB-backed)
                    post_data = {
                        "content": res["content"],
                        "image_urls": res.get("image_urls", []),
                        "platforms": {"community": True, "linkedin": True, "instagram": True},
                    }
                    session_store.save_session(
                        chat_id, post_data, stage="preview", job_id=res.get("job_id")
                    )

                    self.tg_client.send_to_publisher(
                        "✅ *Generation Complete!* Reviewing below:",
                        publisher_token=self.listener_token, chat_id=chat_id
                    )
                    self.send_preview_with_controls(chat_id)
                    logger.info(f"🏁 Ready for review (job #{res.get('job_id')})")
                else:
                    self.tg_client.send_to_publisher(
                        f"❌ *Processing failed:* {task.error}",
                        publisher_token=self.listener_token, chat_id=chat_id
                    )

            # Submit to task worker
            task = Task(
                TaskType.CONTENT_GENERATION,
                payload={"text": input_text, "user_id": user_id, "type": input_type},
                user_id=user_id,
                chat_id=chat_id,
                callback=pipeline_callback
            )
            task_worker.submit(task, self.pipeline.process, input_text, user_id, input_type)

        except Exception as e:
            logger.error(f"Failed to submit task: {e}", exc_info=True)
            self.tg_client.send_to_publisher(
                f"❌ *Queue Error:* {e}",
                publisher_token=self.listener_token, chat_id=chat_id
            )

    def send_preview_with_controls(self, chat_id: int, message_id: int = None):
        """Send or update the preview message with interactive controls."""
        post = session_store.get_session(chat_id)
        if not post:
            return

        content = post["content"]
        platforms = post.get("platforms", {})

        # Escape markdown characters
        def safe(text):
            return text[:150].replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("`", "\\`")

        preview_text = (
            "🧐 *CONTENT PREVIEW & CONTROLS*\n\n"
            f"*💼 LinkedIn:* {safe(content.get('linkedin_post', ''))}...\n\n"
            f"*📸 Instagram:* {safe(content.get('instagram_caption', ''))}...\n\n"
            f"*👥 Community:* {safe(content.get('community_post', ''))}...\n\n"
            f"🎯 *TARGETS:* {' '.join([p.upper() for p, val in platforms.items() if val]) or 'None'}"
        )

        def get_btn(label, key):
            icon = "✅" if platforms.get(key) else "❌"
            return {"text": f"{icon} {label}", "callback_data": f"toggle_{key}"}

        keyboard = {
            "inline_keyboard": [
                [get_btn("LinkedIn", "linkedin"), get_btn("Instagram", "instagram"), get_btn("Community", "community")],
                [{"text": "✍️ Edit Content", "callback_data": "edit_start"}],
                [
                    {"text": "🚀 Confirm & Post", "callback_data": "confirm"},
                    {"text": "🗑️ Cancel", "callback_data": "cancel"}
                ]
            ]
        }

        if message_id:
            self.tg_client.edit_message_text(
                preview_text, message_id, reply_markup=keyboard,
                chat_id=chat_id, token=self.listener_token
            )
        else:
            # Send carousel images first
            if post.get("image_urls"):
                import requests as req
                payload = {
                    "chat_id": chat_id,
                    "media": [{"type": "photo", "media": f"attach://p{i}"} for i in range(len(post["image_urls"]))],
                }
                files = {f"p{i}": open(p, "rb") for i, p in enumerate(post["image_urls"])}
                try:
                    req.post(
                        f"https://api.telegram.org/bot{self.listener_token}/sendMediaGroup",
                        data={"chat_id": chat_id, "media": json.dumps(payload["media"])},
                        files=files
                    )
                finally:
                    for f in files.values():
                        f.close()

            self.tg_client.send_to_publisher(
                preview_text, reply_markup=keyboard,
                publisher_token=self.listener_token, chat_id=chat_id
            )

    def process_revision(self, chat_id: int, revision_prompt: str):
        """Regenerate content based on user feedback."""
        post = session_store.get_session(chat_id)
        if not post:
            return

        self.tg_client.send_to_publisher(
            "🔄 *Regenerating content with your feedback...*",
            publisher_token=self.listener_token, chat_id=chat_id
        )

        try:
            old_content = post["content"]
            refinement_prompt = (
                f"ORIGINAL CONTENT: {json.dumps(old_content)}\n"
                f"USER REVISION REQUEST: {revision_prompt}\n\n"
                f"Rewrite the content according to these instructions. Stay in the exact same JSON format."
            )

            from ai.gemini_engine import GeminiEngine
            engine = GeminiEngine()
            new_content = engine.generate_content(refinement_prompt)

            post["content"] = new_content
            session_store.save_session(chat_id, post, stage="preview", job_id=post.get("job_id"))

            self.send_preview_with_controls(chat_id)
        except Exception as e:
            logger.error(f"Revision error: {e}")
            self.tg_client.send_to_publisher(
                f"❌ *Regeneration failed:* {e}",
                publisher_token=self.listener_token, chat_id=chat_id
            )
            session_store.update_stage(chat_id, "preview")

    def handle_approval(self, chat_id: int, data: str, message_id: int = None):
        """Process user decisions from inline buttons."""
        post = session_store.get_session(chat_id)
        if not post:
            self.tg_client.send_to_publisher(
                "⚠️ *No pending post found or it expired.*",
                publisher_token=self.listener_token, chat_id=chat_id
            )
            return

        if data.startswith("toggle_"):
            platform = data.split("_")[1]
            post["platforms"][platform] = not post["platforms"].get(platform, False)
            session_store.save_session(chat_id, post, stage="preview", job_id=post.get("job_id"))
            self.send_preview_with_controls(chat_id, message_id)

        elif data == "edit_start":
            session_store.update_stage(chat_id, "edit")
            self.tg_client.send_to_publisher(
                "✍️ *Enter your revision requests:*",
                publisher_token=self.listener_token, chat_id=chat_id
            )

        elif data == "confirm":
            self.tg_client.send_to_publisher(
                "🚀 *Publishing to selected platforms...*",
                publisher_token=self.listener_token, chat_id=chat_id
            )
            job_id = post.get("job_id")

            try:
                platforms = post.get("platforms", {})

                if platforms.get("community"):
                    self.tg_client.send_community_post(post["content"], token=self.publisher_token)
                    if job_id:
                        self.pipeline.record_publish(job_id, "community", True)

                if platforms.get("linkedin"):
                    try:
                        self.linkedin_client.publish(post["content"])
                        if job_id:
                            self.pipeline.record_publish(job_id, "linkedin", True)
                    except Exception as e:
                        logger.error(f"LinkedIn publish error: {e}")
                        if job_id:
                            self.pipeline.record_publish(job_id, "linkedin", False, str(e))

                if platforms.get("instagram"):
                    logger.info("Instagram publishing...")
                    # Note: Instagram Graph API requires a public URL for the image.
                    # For local testing, we log the attempt. In prod, the image_urls would be public URLs.
                    if post.get("image_urls"):
                        img_to_publish = post["image_urls"][0] # Just the first one for now
                        try:
                            # If it's a local path, we can't send it to Instagram API directly
                            if not img_to_publish.startswith("http"):
                                logger.warning("Cannot publish local image to Instagram — requires public URL")
                                self.tg_client.send_to_publisher(
                                    "⚠️ *Instagram:* Local images cannot be published via API (requires public URL).",
                                    publisher_token=self.listener_token, chat_id=chat_id
                                )
                            else:
                                self.instagram_client.publish_photo(
                                    img_to_publish,
                                    post["content"].get("instagram_caption", ""),
                                    post["content"].get("trending_hashtags", [])
                                )
                                if job_id:
                                    self.pipeline.record_publish(job_id, "instagram", True)
                        except Exception as e:
                            logger.error(f"Instagram publish error: {e}")
                            if job_id:
                                self.pipeline.record_publish(job_id, "instagram", False, str(e))

                self.tg_client.send_to_publisher(
                    "✅ *Successfully published to selected platforms!*",
                    publisher_token=self.listener_token, chat_id=chat_id
                )
                session_store.delete_session(chat_id)

            except Exception as e:
                logger.error(f"Publishing error: {e}")
                self.tg_client.send_to_publisher(
                    f"❌ *Publishing failed:* {e}",
                    publisher_token=self.listener_token, chat_id=chat_id
                )

        elif data == "cancel":
            session_store.delete_session(chat_id)
            self.tg_client.send_to_publisher(
                "❌ *Post cancelled and cleared.*",
                publisher_token=self.listener_token, chat_id=chat_id
            )
