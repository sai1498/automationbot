import os
import time
import requests
import json
from src.config import Config
from src.engine import ContentEngine
from src.telegram_client import TelegramClient
from src.discord_client import DiscordClient
from src.image_engine import ImageEngine
from src.linkedin_client import LinkedInClient
from src.instagram_client import InstagramClient
from src.transcriber import AudioTranscriber
from src.vision_engine import VisionEngine
from src.visual_processor import VisualProcessor
from src.link_scraper import LinkScraper
import re

class PublisherBot:
    def __init__(self):
        # The Listener Bot is where the user sends news (Input Bot)
        self.listener_token = Config.TELEGRAM_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.listener_token}"
        
        # The Publisher Bot is where previews and approvals happen (Output Bot)
        self.publisher_token = Config.PUBLISHER_BOT_TOKEN or Config.TELEGRAM_TOKEN
        print(f"DEBUG: PublisherBot Initialized.")
        print(f"DEBUG: Listener Token (Input): {self.listener_token[:10]}...")
        print(f"DEBUG: Publisher Token (Output): {self.publisher_token[:10]}...")
        
        # Engines and Clients
        self.engine = ContentEngine()
        self.tg_client = TelegramClient()
        self.discord_client = DiscordClient()
        self.image_engine = ImageEngine()
        self.linkedin_client = LinkedInClient()
        self.instagram_client = InstagramClient()
        self.transcriber = AudioTranscriber()
        self.vision_engine = VisionEngine()
        self.visual_processor = VisualProcessor()
        self.link_scraper = LinkScraper()
        
        # State management for Review Loop
        self.pending_posts = {} # {chat_id: {content, image_urls, platforms, stage}}
        # stages: "preview", "edit"
        
        self.offset = 0

    def get_updates(self):
        url = f"{self.base_url}/getUpdates" # base_url now uses listener_token
        params = {"offset": self.offset, "timeout": 30}
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json().get("result", [])

    def process_message(self, message):
        chat_id = message.get("chat", {}).get("id")
        print(f"📥 Received message from {chat_id}")
        
        # Basic security
        if str(chat_id) != str(Config.TELEGRAM_CHAT_ID):
            print(f"🛑 Security Blocked: Chat ID {chat_id} != Config {Config.TELEGRAM_CHAT_ID}")
            return

        input_text = ""
        
        # 0. Detect Multi-Modal Input
        if "voice" in message:
            print("🎤 Processing Voice Note...")
            self.tg_client.send_to_publisher("🎤 *Voice note detected. Transcribing...*", publisher_token=self.listener_token, chat_id=chat_id)
            file_info = self.tg_client.get_file(message["voice"]["file_id"], token=self.listener_token)
            print(f"DEBUG: File Info: {file_info}")
            local_path = self.tg_client.download_file(file_info["file_path"], "temp_voice.ogg", token=self.listener_token)
            print(f"DEBUG: Downloaded to {local_path}")
            input_text = self.transcriber.transcribe(local_path)
            print(f"DEBUG: Transcription complete: {input_text[:50]}...")
            self.tg_client.send_to_publisher(f"📝 *Transcribed:* \"{input_text[:100]}...\"", publisher_token=self.listener_token, chat_id=chat_id)
            
        elif "photo" in message:
            print("📸 Processing Photo...")
            self.tg_client.send_to_publisher("🖼️ *Photo detected. Analyzing vision...*", publisher_token=self.listener_token, chat_id=chat_id)
            # Get highest resolution photo
            photo = message["photo"][-1]
            file_info = self.tg_client.get_file(photo["file_id"], token=self.listener_token)
            print(f"DEBUG: File Info: {file_info}")
            local_path = self.tg_client.download_file(file_info["file_path"], "temp_vision.jpg", token=self.listener_token)
            print(f"DEBUG: Downloaded to {local_path}")
            input_text = self.vision_engine.analyze_image(local_path)
            print(f"DEBUG: Vision Analysis complete: {input_text[:50]}...")
            self.tg_client.send_to_publisher(f"👁️ *Vision Analysis:* \"{input_text[:100]}...\"", publisher_token=self.listener_token, chat_id=chat_id)
            
        elif "text" in message:
            print(f"✍️ Processing Text: {message['text'][:50]}...")
            input_text = message["text"]
            # Check for URL
            urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-A][0-9a-fA-A]))+', input_text)
            if urls:
                self.tg_client.send_to_publisher(f"🔗 *URL detected. Scraping {urls[0]}...*", publisher_token=self.listener_token, chat_id=chat_id)
                input_text = self.link_scraper.scrape(urls[0])
        
        if not input_text:
            return

        print(f"🚀 Processing Input: {input_text[:50]}...")
        self.tg_client.send_to_publisher("⚙️ *Starting multi-platform processing flow...*", publisher_token=self.listener_token, chat_id=chat_id)
        
        try:
            # 1. Generate Content
            content = self.engine.generate_content(input_text)
            
            # 2. Generate Images & Overlay Text
            final_media_paths = []
            if not content.get("is_community_only"):
                 print("🎨 Generating cinematic images...")
                 self.tg_client.send_to_publisher("🎨 *Generating cinematic images...*", publisher_token=self.listener_token, chat_id=chat_id)
                 time.sleep(1) # Delay
                 base_image_urls = self.image_engine.generate_carousel_images(content['image_prompts'])
                 
                 print("✍️ Overlaying slide text on images...")
                 self.tg_client.send_to_publisher("✍️ *Overlaying slide text on visuals...*", publisher_token=self.listener_token, chat_id=chat_id)
                 time.sleep(1) # Delay
                 final_media_paths = self.visual_processor.process_carousel(base_image_urls, content['carousel_slides'])
            
            # 3. Store in State for Review
            self.pending_posts[chat_id] = {
                "content": content,
                "image_urls": final_media_paths,
                "platforms": {"community": True, "linkedin": True, "instagram": True},
                "stage": "preview"
            }

            self.tg_client.send_to_publisher("✅ *Generation Complete!* Reviewing text and visuals below:", publisher_token=self.listener_token, chat_id=chat_id)
            self.send_preview_with_controls(chat_id)
            print("🏁 Ready for user review.")
            
        except Exception as e:
            print(f"Error: {e}")
            self.tg_client.send_to_publisher(f"❌ *Total Loop Failure:* {e}", publisher_token=self.listener_token, chat_id=chat_id)

    def send_preview_with_controls(self, chat_id, message_id=None):
        """Sends or updates the preview message with interactive toggles."""
        post = self.pending_posts.get(chat_id)
        if not post: return

        content = post['content']
        platforms = post['platforms']
        
        # Basic escaping for Markdown
        safe_linkedin = content['linkedin_post'][:150].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
        safe_insta = content['instagram_caption'][:150].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
        safe_comm = content['community_post'][:150].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')

        preview_text = (
            "🧐 *CONTENT PREVIEW & CONTROLS*\n\n"
            f"*💼 LinkedIn:* {safe_linkedin}...\n\n"
            f"*📸 Instagram:* {safe_insta}...\n\n"
            f"*👥 Community:* {safe_comm}...\n\n"
            f"🎯 *TARGETS:* {' '.join([p.upper() for p, val in platforms.items() if val]) or 'None'}"
        )

        def get_btn(label, key):
            icon = "✅" if platforms[key] else "❌"
            return {"text": f"{icon} {label}", "callback_data": f"toggle_{key}"}

        keyboard = {
            "inline_keyboard": [
                [get_btn("LinkedIn", "linkedin"), get_btn("Instagram", "instagram"), get_btn("Community", "community")],
                [{"text": "✍️ Edit Content", "callback_data": "edit_start"}],
                [{"text": "🚀 Confirm & Post Selected", "callback_data": "confirm"},
                 {"text": "🗑️ Cancel", "callback_data": "cancel"}]
            ]
        }

        if message_id:
            # If we are just toggling, we only update the text/buttons message
            self.tg_client.edit_message_text(preview_text, message_id, reply_markup=keyboard, chat_id=chat_id, token=self.listener_token)
        else:
            # If it's a new preview, send the carousel first if it exists
            if post.get('image_urls'):
                payload = {
                    "chat_id": chat_id,
                    "media": [{"type": "photo", "media": f"attach://p{i}"} for i in range(len(post['image_urls']))],
                }
                files = {f"p{i}": open(p, "rb") for i, p in enumerate(post['image_urls'])}
                requests.post(f"https://api.telegram.org/bot{self.listener_token}/sendMediaGroup", data={"chat_id": chat_id, "media": json.dumps(payload["media"])}, files=files)
                for f in files.values(): f.close()
            
            # Then send the control message
            self.tg_client.send_to_publisher(preview_text, reply_markup=keyboard, publisher_token=self.listener_token, chat_id=chat_id)

    def process_revision(self, chat_id, revision_prompt):
        """Regenerates content based on user feedback."""
        post = self.pending_posts.get(chat_id)
        if not post: return

        self.tg_client.send_to_publisher("🔄 *Regenerating content with your feedback...*", publisher_token=self.listener_token, chat_id=chat_id)
        
        try:
            old_content = post['content']
            # We ask Gemini to take the old content and the revision instructions
            refinement_prompt = f"""
            ORIGINAL CONTENT: {json.dumps(old_content)}
            USER REVISION REQUEST: {revision_prompt}
            
            Please rewrite the content according to these instructions. Stay in the exact same JSON format.
            """
            
            new_content = self.engine.generate_content(refinement_prompt)
            
            # Update state
            post['content'] = new_content
            post['stage'] = "preview"
            
            # Note: We keep the old images for now
            self.send_preview_with_controls(chat_id)
        except Exception as e:
            self.tg_client.send_to_publisher(f"❌ *Regeneration failed:* {e}", publisher_token=self.listener_token, chat_id=chat_id)
            post['stage'] = "preview"

    def handle_approval(self, chat_id, data, message_id=None):
        """Processes the user's decision from the inline buttons."""
        post = self.pending_posts.get(chat_id)
        if not post:
            self.tg_client.send_to_publisher("⚠️ *No pending post found or it expired.*", publisher_token=self.listener_token, chat_id=chat_id)
            return

        if data.startswith("toggle_"):
            platform = data.split("_")[1]
            post['platforms'][platform] = not post['platforms'][platform]
            self.send_preview_with_controls(chat_id, message_id)

        elif data == "edit_start":
            post['stage'] = "edit"
            self.tg_client.send_to_publisher("✍️ *Enter your revision requests:* (e.g. 'Make the LinkedIn post more aggressive' or 'Change the headline')", publisher_token=self.listener_token, chat_id=chat_id)

        elif data == "confirm":
            self.tg_client.send_to_publisher("🚀 *Approving and blasting to platforms...*", publisher_token=self.listener_token, chat_id=chat_id)
            
            try:
                platforms = post['platforms']
                # Deliver ONLY Community content to the Output Bot if selected
                if platforms.get('community'):
                    self.tg_client.send_community_post(post['content'], token=self.publisher_token)
                
                # Deliver to Discord if selected
                if platforms.get('discord') and Config.DISCORD_WEBHOOK_URL: # Discord toggle not in UI yet but ready
                    self.discord_client.send_content_package(post['content'])
                
                # Deliver to LinkedIn/Instagram (placeholder for real API calls)
                if platforms.get('linkedin'):
                     print("Posting to LinkedIn API...")
                     from src.linkedin_client import LinkedInClient
                     li_client = LinkedInClient()
                     li_client.publish(post['content'])
                if platforms.get('instagram'):
                     print("Posting to Instagram API...")
                     from src.instagram_client import InstagramClient
                     insta_client = InstagramClient()
                     # Note: Instagram requires image URLs, but for now we log.
                     # insta_client.publish(post['content'], post['image_urls'])
                
                self.tg_client.send_to_publisher("✅ *Successfully published to selected platforms!*", publisher_token=self.listener_token, chat_id=chat_id)
                del self.pending_posts[chat_id]
            except Exception as e:
                self.tg_client.send_to_publisher(f"❌ *Publishing failed:* {e}", publisher_token=self.listener_token, chat_id=chat_id)

        elif data == "cancel":
            if chat_id in self.pending_posts:
                del self.pending_posts[chat_id]
            self.tg_client.send_to_publisher("❌ *Post cancelled and cleared.*", publisher_token=self.publisher_token, chat_id=chat_id)

    def run(self):
        print("🌍 Publisher Bot is ACTIVE. Listening for news...")
        while True:
            try:
                updates = self.get_updates()
                if updates:
                    print(f"🔄 Found {len(updates)} updates.")
                for update in updates:
                    self.offset = update["update_id"] + 1
                    
                    if "message" in update:
                        msg = update["message"]
                        cid = msg["chat"]["id"]
                        if cid in self.pending_posts and self.pending_posts[cid].get('stage') == 'edit':
                            # Process revision request
                            self.process_revision(cid, msg.get('text'))
                        else:
                            self.process_message(msg)
                    elif "callback_query" in update:
                        # Handle button clicks
                        chat_id = update["callback_query"]["message"]["chat"]["id"]
                        message_id = update["callback_query"]["message"]["message_id"]
                        data = update["callback_query"]["data"]
                        self.handle_approval(chat_id, data, message_id)
                        
            except Exception as e:
                print(f"Listener error: {e}")
                time.sleep(5)
            time.sleep(1)

if __name__ == "__main__":
    listener = PublisherBot()
    listener.run()
