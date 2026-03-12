import os
import requests
import time
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import textwrap

class VisualProcessor:
    def __init__(self):
        # Default font paths for Windows
        self.font_path = "C:\\Windows\\Fonts\\arialbd.ttf" # Bold Arial for main text
        self.temp_dir = "temp_processing"
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    def _download_image(self, url, idx):
        path = os.path.join(self.temp_dir, f"base_{int(time.time())}_{idx}.png")
        response = requests.get(url)
        response.raise_for_status()
        with open(path, "wb") as f:
            f.write(response.content)
        return path

    def overlay_text(self, image_url, text, index):
        """Downloads an image, overlays text, and returns the path to the processed image."""
        base_path = self._download_image(image_url, index)
        img = Image.open(base_path).convert("RGBA")
        
        # Darken the image slightly for better contrast
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(0.7)
        
        draw = ImageDraw.Draw(img)
        width, height = img.size
        
        # Font settings
        title_font_size = 60
        sub_font_size = 40
        
        try:
            title_font = ImageFont.truetype(self.font_path, title_font_size)
        except:
            title_font = ImageFont.load_default()

        # Wrap text
        wrapper = textwrap.TextWrapper(width=30) # Approx chars per line
        lines = wrapper.wrap(text=text)
        
        # Calculate Y start position (center-ish)
        total_text_height = len(lines) * (title_font_size + 10)
        current_y = (height - total_text_height) // 2
        
        # Add a semi-transparent black overlay for better readability behind the text
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        # Rectangle covering the text area
        rect_margin = 40
        overlay_draw.rectangle([rect_margin, current_y - rect_margin, width - rect_margin, current_y + total_text_height + rect_margin], fill=(0, 0, 0, 160))
        img = Image.alpha_composite(img, overlay)
        draw = ImageDraw.Draw(img) # Redraw on composite

        for line in lines:
            # Center horizontally
            bbox = draw.textbbox((0, 0), line, font=title_font)
            text_width = bbox[2] - bbox[0]
            current_x = (width - text_width) // 2
            
            # Draw text with shadow
            draw.text((current_x + 3, current_y + 3), line, font=title_font, fill=(0, 0, 0, 255)) # Shadow
            draw.text((current_x, current_y), line, font=title_font, fill=(255, 255, 255, 255)) # Actual text
            
            current_y += title_font_size + 10
            
        final_path = os.path.join(self.temp_dir, f"slide_{int(time.time())}_{index}.png")
        img.convert("RGB").save(final_path, "JPEG", quality=95)
        
        # Cleanup base image
        try: os.remove(base_path)
        except: pass
        
        return final_path

    def process_carousel(self, image_urls, slides):
        """Processes a list of image URLs and slide texts."""
        processed_paths = []
        for i, (url, text) in enumerate(zip(image_urls, slides)):
            try:
                processed_path = self.overlay_text(url, text, i+1)
                processed_paths.append(processed_path)
            except Exception as e:
                print(f"Error processing slide {i+1}: {e}")
                # Fallback to base URL if overlay fails? (Or handle error in bot)
        return processed_paths
