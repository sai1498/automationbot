import requests
from src.config import Config

class InstagramClient:
    def __init__(self):
        self.business_account_id = Config.INSTAGRAM_BUSINESS_ACCOUNT_ID
        self.access_token = Config.INSTAGRAM_ACCESS_TOKEN

    def publish_photo(self, image_url, caption, hashtags=[]):
        """Publishes a photo to Instagram."""
        if not self.access_token:
            print("Instagram Access Token missing. Skipping.")
            return

        # 1. Create Container
        container_url = f"https://graph.facebook.com/v18.0/{self.business_account_id}/media"
        full_caption = f"{caption}\n\n" + " ".join(hashtags)
        
        payload = {
            "image_url": image_url,
            "caption": full_caption,
            "access_token": self.access_token
        }
        
        res = requests.post(container_url, data=payload)
        res.raise_for_status()
        creation_id = res.json().get("id")

        # 2. Publish Container
        publish_url = f"https://graph.facebook.com/v18.0/{self.business_account_id}/media_publish"
        publish_payload = {
            "creation_id": creation_id,
            "access_token": self.access_token
        }
        
        final_res = requests.post(publish_url, data=publish_payload)
        final_res.raise_for_status()
        return final_res.json()
