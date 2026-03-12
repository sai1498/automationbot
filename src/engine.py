import json
import google.generativeai as genai
from src.config import Config

class ContentEngine:
    def __init__(self):
        self._initialize_gemini()

    def _initialize_gemini(self):
        if not Config.GOOGLE_API_KEY:
            print("Warning: GOOGLE_API_KEY missing.")
            return
        genai.configure(api_key=Config.GOOGLE_API_KEY)
        # We use Flash for text generation as it's optimized for structured JSON and speed
        self.model = genai.GenerativeModel(
            model_name=Config.GEMINI_MODEL,
            generation_config={"response_mime_type": "application/json"}
        )

    def generate_content(self, news_input):
        is_community_only = news_input.strip().upper().startswith("[COMMUNITY]")
        
        system_prompt = f"""You are a geopolitical financial content engine.
Your task is to convert news into several formats.

1. LinkedIn post: professional, analytical, institutional tone.
2. Instagram caption: short, emotional, hook-based, trader mindset.
3. Community post: friendly, discussion-driven.
4. 5-Slide Carousel: Enforce < 15 words per slide.
5. 5 Cinematic Image Prompts.
6. Trending Hashtags: 5-10 contextually relevant, high-traffic hashtags for finance/geopolitics.

{"[STRICT MODE: COMMUNITY ONLY] Only generate the 'community_post' and 'trending_hashtags'. Leave all other fields (linkedin_post, instagram_caption, carousel_slides, image_prompts) as empty strings or empty lists." if is_community_only else ""}

Output a JSON object with this structure:
{{
"is_community_only": {str(is_community_only).lower()},
"linkedin_post": "...",
"instagram_caption": "...",
"community_post": "...",
"carousel_slides": ["slide 1", ...],
"image_prompts": ["prompt 1", ...],
"trending_hashtags": ["#hashtag1", ...]
}}"""

        prompt = f"{system_prompt}\n\nINPUT NEWS:\n{news_input}"
        
        try:
            response = self.model.generate_content(prompt)
            return json.loads(response.text)
        except Exception as e:
            print(f"Gemini Error: {e}")
            raise
