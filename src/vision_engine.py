import google.generativeai as genai
from PIL import Image
from src.config import Config

class VisionEngine:
    def __init__(self):
        if not Config.GOOGLE_API_KEY:
            print("Warning: GOOGLE_API_KEY missing.")
            return
        genai.configure(api_key=Config.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(model_name=Config.GEMINI_MODEL)

    def analyze_image(self, image_path):
        """Analyzes an image and extracts geopolitical/financial context using Gemini."""
        try:
            img = Image.open(image_path)
            prompt = "Analyze this image and describe the geopolitical or financial event, data, or news it contains. Provide a comprehensive summary that can be used to generate social media content."
            
            response = self.model.generate_content([prompt, img])
            return response.text
        except Exception as e:
            print(f"Gemini Vision Error: {e}")
            raise
