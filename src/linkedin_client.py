import requests
from src.config import Config

class LinkedInClient:
    def __init__(self):
        self.access_token = Config.LINKEDIN_ACCESS_TOKEN
        self.person_id = Config.LINKEDIN_PERSON_ID
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }

    def post_content(self, text, hashtags=[]):
        """Posts content to LinkedIn."""
        if not self.access_token:
            print("LinkedIn Access Token missing. Skipping.")
            return

        url = "https://api.linkedin.com/v2/ugcPosts"
        full_text = f"{text}\n\n" + " ".join(hashtags)
        
        payload = {
            "author": f"urn:li:person:{self.person_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": full_text
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()
