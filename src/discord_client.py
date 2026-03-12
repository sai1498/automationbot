import requests
from src.config import Config

class DiscordClient:
    def __init__(self):
        self.webhook_url = Config.DISCORD_WEBHOOK_URL

    def send_message(self, content):
        if not self.webhook_url:
            print("Discord Webhook URL not configured. Skipping Discord.")
            return
            
        payload = {"content": content}
        response = requests.post(self.webhook_url, json=payload)
        response.raise_for_status()
        return response

    def send_content_package(self, content_json):
        """Formats and sends the content to Discord."""
        is_community_only = content_json.get("is_community_only", False)
        
        if is_community_only:
            message = f"**👥 Community Discussion**\n\n{content_json['community_post']}"
            self.send_message(message)
        else:
            # Send Analysis and Community for standard news
            analysis = (
                f"**💼 LinkedIn Analysis**\n{content_json['linkedin_post']}\n\n"
                f"**📸 Instagram Hook**\n{content_json['instagram_caption']}\n\n"
                f"**👥 Community Discussion**\n{content_json['community_post']}"
            )
            self.send_message(analysis)
            
            # Send Slides
            slides = "**📊 Carousel Slides**\n" + "\n".join([f"Slide {i+1}: {slide}" for i, slide in enumerate(content_json['carousel_slides'])])
            self.send_message(slides)
