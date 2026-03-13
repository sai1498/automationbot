"""
Image analysis (vision) using Gemini.
Moved from src/vision_engine.py with retry logic.
"""

import logging
import google.generativeai as genai
from PIL import Image
from config.settings import Config
from core.retry import retry_with_backoff
from ai.prompt_builder import VISION_ANALYSIS_PROMPT

logger = logging.getLogger(__name__)


class ImageParser:
    """Analyzes images for geopolitical/financial context using Gemini Vision."""

    def __init__(self):
        self.model = None
        if not Config.GOOGLE_API_KEY:
            logger.warning("GOOGLE_API_KEY missing — vision analysis disabled")
            return
        genai.configure(api_key=Config.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(model_name=Config.GEMINI_MODEL)
        logger.info("✅ ImageParser initialized")

    @retry_with_backoff(max_attempts=3, base_delay=2.0)
    def analyze_image(self, image_path: str) -> str:
        """Analyze an image and extract context."""
        if not self.model:
            raise RuntimeError("ImageParser not initialized")

        img = Image.open(image_path)
        response = self.model.generate_content([VISION_ANALYSIS_PROMPT, img])
        logger.info("✅ Image analysis complete")
        return response.text
