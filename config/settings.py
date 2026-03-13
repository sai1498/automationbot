"""
Centralized configuration with validation.
All settings loaded from .env file via python-dotenv.
"""

import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Config:
    """Application configuration — loaded once at startup."""

    # ─── AI / LLM ────────────────────────────────────────────
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    GEMINI_PRO_MODEL = os.getenv("GEMINI_PRO_MODEL", "gemini-2.5-pro-preview-05-06")

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")

    # ─── Telegram ────────────────────────────────────────────
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    PUBLISHER_BOT_TOKEN = os.getenv("PUBLISHER_BOT_TOKEN")
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

    # ─── Social Media ────────────────────────────────────────
    DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
    LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN")
    LINKEDIN_PERSON_ID = os.getenv("LINKEDIN_PERSON_ID")
    INSTAGRAM_BUSINESS_ACCOUNT_ID = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")

    # ─── Security ────────────────────────────────────────────
    ALLOWED_USERS: list[int] = []
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))

    # ─── Database ────────────────────────────────────────────
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/bot.db")

    # ─── Logging ─────────────────────────────────────────────
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # ─── Performance ─────────────────────────────────────────
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))
    CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "24"))

    @classmethod
    def _parse_allowed_users(cls):
        """Parse ALLOWED_USERS from comma-separated env var."""
        raw = os.getenv("ALLOWED_USERS", "")
        if raw.strip():
            cls.ALLOWED_USERS = [int(uid.strip()) for uid in raw.split(",") if uid.strip()]

    @classmethod
    def validate(cls):
        """Validate critical configuration on startup."""
        cls._parse_allowed_users()

        warnings = []
        errors = []

        # Critical
        if not cls.TELEGRAM_TOKEN:
            errors.append("TELEGRAM_TOKEN is required")
        if not cls.GOOGLE_API_KEY:
            warnings.append("GOOGLE_API_KEY missing — AI features will be disabled")

        # Optional but important
        if not cls.TELEGRAM_CHAT_ID:
            warnings.append("TELEGRAM_CHAT_ID not set — chat ID security check disabled")
        if not cls.ALLOWED_USERS:
            warnings.append("ALLOWED_USERS not set — any Telegram user can interact with the bot")
        if not cls.WEBHOOK_SECRET:
            warnings.append("WEBHOOK_SECRET not set — webhook requests won't be verified")

        for w in warnings:
            logger.warning(f"⚠️  Config: {w}")
        for e in errors:
            logger.error(f"❌ Config: {e}")

        if errors:
            logger.error("Fatal configuration errors. Exiting.")
            sys.exit(1)

        logger.info("✅ Configuration validated successfully")
