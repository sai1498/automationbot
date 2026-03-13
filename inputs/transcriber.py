"""
Audio transcription using Gemini.
Moved from src/transcriber.py with retry logic.
"""

import time
import logging
import google.generativeai as genai
from config.settings import Config
from core.retry import retry_with_backoff
from ai.prompt_builder import TRANSCRIPTION_PROMPT

logger = logging.getLogger(__name__)


class AudioTranscriber:
    """Transcribes audio files using Gemini 1.5 Pro."""

    def __init__(self):
        self.model = None
        if not Config.GOOGLE_API_KEY:
            logger.warning("GOOGLE_API_KEY missing — transcription disabled")
            return
        genai.configure(api_key=Config.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(model_name=Config.GEMINI_PRO_MODEL)
        logger.info("✅ AudioTranscriber initialized")

    @retry_with_backoff(max_attempts=3, base_delay=2.0)
    def transcribe(self, file_path: str) -> str:
        """Transcribe an audio file."""
        if not self.model:
            raise RuntimeError("Transcriber not initialized")

        logger.info(f"🎤 Uploading audio: {file_path}")
        audio_file = genai.upload_file(path=file_path)

        # Wait for processing
        while audio_file.state.name == "PROCESSING":
            time.sleep(2)
            audio_file = genai.get_file(audio_file.name)

        if audio_file.state.name == "FAILED":
            raise Exception("Audio file processing failed on Gemini")

        response = self.model.generate_content([audio_file, TRANSCRIPTION_PROMPT])

        # Cleanup remote file
        try:
            genai.delete_file(audio_file.name)
        except Exception:
            pass

        logger.info("✅ Transcription complete")
        return response.text
