"""
Image generation engine using Google Imagen API.
Moved from src/image_engine.py with parallel generation and retry logic.
"""

import os
import base64
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from config.settings import Config
from core.retry import retry_with_backoff
from ai.prompt_builder import IMAGE_STYLE_SUFFIX

logger = logging.getLogger(__name__)


class ImageEngine:
    """Generates images using Google Imagen REST API with parallel processing."""

    MODELS_TO_TRY = [
        "imagen-4.0-generate-001",
        "imagen-4.0-fast-generate-001",
        "gemini-2.0-flash-exp-image-generation",
    ]

    def __init__(self):
        self.api_key = Config.GOOGLE_API_KEY
        self.output_dir = "temp_processing"
        os.makedirs(self.output_dir, exist_ok=True)

    @retry_with_backoff(max_attempts=2, base_delay=3.0)
    def generate_image(self, prompt: str, index: int = 0) -> str:
        """Generate a single image, trying multiple models as fallback."""
        logger.info(f"🎨 Generating image #{index}: {prompt[:50]}...")

        last_error = ""
        for model in self.MODELS_TO_TRY:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:predict?key={self.api_key}"
                payload = {
                    "instances": [{"prompt": prompt}],
                    "parameters": {"sampleCount": 1}
                }

                response = requests.post(url, json=payload, timeout=60)
                if response.status_code == 200:
                    data = response.json()
                    if "predictions" in data and data["predictions"]:
                        img_data = base64.b64decode(data["predictions"][0]["bytesBase64Encoded"])
                        path = os.path.join(self.output_dir, f"img_{int(time.time())}_{index}.png")
                        with open(path, "wb") as f:
                            f.write(img_data)
                        logger.info(f"✅ Image #{index} generated with {model}")
                        return path
                else:
                    last_error = f"{model}: {response.status_code} - {response.text[:200]}"
                    logger.warning(f"⚠️ {model} failed: {response.status_code}")
            except Exception as e:
                last_error = f"{model}: {e}"
                continue

        raise Exception(f"All Imagen models failed. Last error: {last_error}")

    def generate_carousel_images(self, prompts: list[str]) -> list[str]:
        """Generate images in parallel using ThreadPoolExecutor."""
        image_paths = []
        styled_prompts = [f"{p}{IMAGE_STYLE_SUFFIX}" for p in prompts]

        with ThreadPoolExecutor(max_workers=Config.MAX_WORKERS) as executor:
            futures = {
                executor.submit(self.generate_image, prompt, i): i
                for i, prompt in enumerate(styled_prompts)
            }

            results = {}
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    path = future.result()
                    results[idx] = path
                except Exception as e:
                    logger.error(f"Error generating image #{idx}: {e}")

        # Return in order
        for i in range(len(prompts)):
            if i in results:
                image_paths.append(results[i])

        logger.info(f"✅ Generated {len(image_paths)}/{len(prompts)} carousel images")
        return image_paths
