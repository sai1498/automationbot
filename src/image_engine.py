import requests
import os
import json
import base64
import time
from src.config import Config

class ImageEngine:
    def __init__(self):
        self.api_key = Config.GOOGLE_API_KEY
        self.model_id = "imagen-3.1-flash" # Trying flash first as it's common in AI Studio
        # Or 'imagen-3.0-generate-001'

    def generate_image(self, prompt, index=0):
        """Generates a single image using Google Imagen REST API."""
        print(f"🎨 Generating Imagen image: {prompt[:50]}...")
        
        # Verified available models from audit
        models_to_try = [
            "imagen-4.0-generate-001",
            "imagen-4.0-fast-generate-001",
            "gemini-2.0-flash-exp-image-generation"
        ]
        
        last_error = ""
        for model in models_to_try:
            try:
                # The full path should be models/model-name
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:predict?key={self.api_key}"
                payload = {
                    "instances": [
                        {"prompt": prompt}
                    ],
                    "parameters": {
                        "sampleCount": 1
                    }
                }
                
                response = requests.post(url, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    # The response format usually contains base64 in 'predictions'
                    if 'predictions' in data and data['predictions']:
                        # AI Studio Imagen response structure: predictions[0]['bytesBase64Encoded']
                        img_data = base64.b64decode(data['predictions'][0]['bytesBase64Encoded'])
                        path = f"generated_image_{int(time.time())}_{index}.png"
                        with open(path, "wb") as f:
                            f.write(img_data)
                        return path
                else:
                    last_error = f"{model} failed: {response.status_code} - {response.text}"
                    print(f"⚠️ Model {model} failed: {response.status_code}")
                    print(f"Error details: {response.text}")
            except Exception as e:
                last_error = str(e)
                continue
                
        raise Exception(f"All Imagen models failed. Last error: {last_error}")

    def generate_carousel_images(self, prompts):
        """Generates local image paths for a list of prompts."""
        image_paths = []
        for i, prompt in enumerate(prompts):
            try:
                styled_prompt = f"{prompt}, cinematic, high-fidelity, financial news aesthetic, professional photography, 8k"
                img_path = self.generate_image(styled_prompt, i)
                image_paths.append(img_path)
            except Exception as e:
                print(f"Error generating visual: {e}")
        return image_paths
