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
        """Build optimized prompt using PromptBuilder templates."""
        from ai.prompt_builder import SYSTEM_PROMPT, MAIN_TASK_PROMPT, COMMUNITY_ONLY_PROMPT

        if is_community_only:
            task = COMMUNITY_ONLY_PROMPT.format(news_input=news_input)
        else:
            task = MAIN_TASK_PROMPT.format(
                is_community_only="false",
                news_input=news_input
            )

        return f"{SYSTEM_PROMPT}\n\n{task}"
