"""
Visual processor — overlays text on images for carousel slides.
Moved from src/visual_processor.py (logic preserved).
"""

import os
import time
import logging

import requests
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import textwrap

logger = logging.getLogger(__name__)


class VisualProcessor:
    """Downloads images and overlays carousel text with cinematic styling."""

    def __init__(self):
        self.font_path = "C:\\Windows\\Fonts\\arialbd.ttf"
        self.temp_dir = "temp_processing"
        os.makedirs(self.temp_dir, exist_ok=True)

    def _download_image(self, url: str, idx: int) -> str:
        path = os.path.join(self.temp_dir, f"base_{int(time.time())}_{idx}.png")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        with open(path, "wb") as f:
            f.write(response.content)
        return path

    def overlay_text(self, image_source: str, text: str, index: int) -> str:
        """Overlay text on an image. Source can be URL or local path."""
        if image_source.startswith(("http://", "https://")):
            base_path = self._download_image(image_source, index)
        else:
            base_path = image_source

        img = Image.open(base_path).convert("RGBA")

        # Darken for contrast
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(0.7)

        draw = ImageDraw.Draw(img)
        width, height = img.size

        title_font_size = 60
        try:
            title_font = ImageFont.truetype(self.font_path, title_font_size)
        except Exception:
            title_font = ImageFont.load_default()

        wrapper = textwrap.TextWrapper(width=30)
        lines = wrapper.wrap(text=text)

        total_text_height = len(lines) * (title_font_size + 10)
        current_y = (height - total_text_height) // 2

        # Semi-transparent overlay
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        rect_margin = 40
        overlay_draw.rectangle(
            [rect_margin, current_y - rect_margin, width - rect_margin, current_y + total_text_height + rect_margin],
            fill=(0, 0, 0, 160)
        )
        img = Image.alpha_composite(img, overlay)
        draw = ImageDraw.Draw(img)

        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=title_font)
            text_width = bbox[2] - bbox[0]
            current_x = (width - text_width) // 2

            # Shadow + text
            draw.text((current_x + 3, current_y + 3), line, font=title_font, fill=(0, 0, 0, 255))
            draw.text((current_x, current_y), line, font=title_font, fill=(255, 255, 255, 255))
            current_y += title_font_size + 10

        final_path = os.path.join(self.temp_dir, f"slide_{int(time.time())}_{index}.png")
        img.convert("RGB").save(final_path, "JPEG", quality=95)

        # Cleanup base if it was a download
        if image_source.startswith(("http://", "https://")):
            try:
                os.remove(base_path)
            except Exception:
                pass

        return final_path

    def process_carousel(self, image_sources: list[str], slides: list[str]) -> list[str]:
        """Process a list of images with slide text overlays."""
        processed = []
        for i, (source, text) in enumerate(zip(image_sources, slides)):
            try:
                path = self.overlay_text(source, text, i + 1)
                processed.append(path)
            except Exception as e:
                logger.error(f"Error processing slide {i + 1}: {e}")
        return processed
