"""
Gemini-powered content generation engine.
Moved from src/engine.py with improved prompt structure and error handling.
"""

import json
import logging
import google.generativeai as genai
from config.settings import Config
from core.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class GeminiEngine:
    """Content generation using Google Gemini."""

    def __init__(self):
        self._initialize()

    def _initialize(self):
        if not Config.GOOGLE_API_KEY:
            logger.warning("GOOGLE_API_KEY missing — AI features disabled")
            self.model = None
            return
        genai.configure(api_key=Config.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(
            model_name=Config.GEMINI_MODEL,
            generation_config={"response_mime_type": "application/json"}
        )
        logger.info(f"✅ Gemini initialized with model: {Config.GEMINI_MODEL}")

    @retry_with_backoff(max_attempts=3, base_delay=2.0)
    def generate_content(self, news_input: str) -> dict:
        """Generate multi-platform content from news input."""
        if not self.model:
            raise RuntimeError("Gemini model not initialized — check GOOGLE_API_KEY")

        is_community_only = news_input.strip().upper().startswith("[COMMUNITY]")

        prompt = self._build_prompt(news_input, is_community_only)

        response = self.model.generate_content(prompt)
        result = json.loads(response.text)
        logger.info(f"✅ Content generated (community_only={is_community_only})")
        return result

    def _build_prompt(self, news_input: str, is_community_only: bool) -> str:
        """Build optimized prompt with SYSTEM/CONTEXT/TASK/FORMAT structure."""

        # SYSTEM
        system = "You are a geopolitical financial content engine."

        # TASK
        if is_community_only:
            task = (
                "[STRICT MODE: COMMUNITY ONLY] "
                "Only generate 'community_post' and 'trending_hashtags'. "
                "Leave all other fields as empty strings or empty lists."
            )
        else:
            task = (
                "Convert the input news into these formats:\n"
                "1. LinkedIn post: professional, analytical, institutional tone.\n"
                "2. Instagram caption: short, emotional, hook-based, trader mindset.\n"
                "3. Community post: friendly, discussion-driven.\n"
                "4. 5-Slide Carousel: Enforce < 15 words per slide.\n"
                "5. 5 Cinematic Image Prompts.\n"
                "6. Trending Hashtags: 5-10 contextually relevant, high-traffic hashtags."
            )

        # OUTPUT FORMAT
        output_format = (
            "Output a JSON object with this structure:\n"
            "{\n"
            f'  "is_community_only": {str(is_community_only).lower()},\n'
            '  "linkedin_post": "...",\n'
            '  "instagram_caption": "...",\n'
            '  "community_post": "...",\n'
            '  "carousel_slides": ["slide 1", ...],\n'
            '  "image_prompts": ["prompt 1", ...],\n'
            '  "trending_hashtags": ["#hashtag1", ...]\n'
            "}"
        )

        return f"{system}\n\n{task}\n\n{output_format}\n\nINPUT NEWS:\n{news_input}"
