import google.generativeai as genai
import time
from src.config import Config

class AudioTranscriber:
    def __init__(self):
        if not Config.GOOGLE_API_KEY:
            print("Warning: GOOGLE_API_KEY missing.")
            return
        genai.configure(api_key=Config.GOOGLE_API_KEY)
        # 1.5 Pro is excellent for audio processing
        self.model = genai.GenerativeModel(model_name=Config.GEMINI_PRO_MODEL)

    def transcribe(self, file_path):
        """Transcribes / Analyzes an audio file using Gemini 1.5."""
        try:
            print(f"Uploading audio file: {file_path}")
            audio_file = genai.upload_file(path=file_path)
            
            # Wait for processing
            while audio_file.state.name == "PROCESSING":
                time.sleep(2)
                audio_file = genai.get_file(audio_file.name)
            
            if audio_file.state.name == "FAILED":
                raise Exception("Audio file processing failed on Gemini.")

            prompt = "Transcribe this audio file accurately and provide a clear summary of any geopolitical or financial news mentioned."
            response = self.model.generate_content([audio_file, prompt])
            
            # Clean up the file from Gemini storage
            genai.delete_file(audio_file.name)
            
            return response.text
        except Exception as e:
            print(f"Gemini Audio Error: {e}")
            raise
