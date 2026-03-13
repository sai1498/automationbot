"""
Bot entry point — initializes all systems and starts the polling loop.

Usage:
    python -m bot.main
"""

import sys
import os
import time
import logging
import requests

# Ensure project root is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import signal
from config.settings import Config
from database.models import init_db
from core.orchestrator import Orchestrator
from bot.handlers import handle_message
from task_queue.worker import task_worker

# ─── Logging Setup ────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOG_DIR, "bot.log"), encoding="utf-8"),
    ]
)
logger = logging.getLogger("bot.main")


def main():
    """Initialize all systems and start the Telegram polling loop."""
    logger.info("=" * 60)
    logger.info("🚀 TELEGRAM AI PUBLISHER BOT — Professional Edition")
    logger.info("=" * 60)

    # 1. Validate configuration
    Config.validate()

    # 2. Initialize database
    init_db()

    # 3. Create orchestrator
    orchestrator = Orchestrator()

    # 4. Graceful Shutdown Handler
    def signal_handler(sig, frame):
        logger.info("🛑 Signal received. Shutting down gracefully...")
        task_worker.shutdown(wait=True)
        logger.info("👋 Bot stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 5. Start polling
    base_url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}"
    offset = 0

    logger.info("🌍 Bot is ACTIVE. Listening for messages...")
    logger.info(f"📊 Rate Limit: {Config.RATE_LIMIT_PER_MINUTE} req/min/user")
    logger.info(f"👥 Allowed Users: {Config.ALLOWED_USERS or 'ALL (no restriction)'}")
    logger.info(f"🗄️  Database: {Config.DATABASE_URL}")

    while True:
        try:
            response = requests.get(
                f"{base_url}/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=35
            )
            response.raise_for_status()
            updates = response.json().get("result", [])

            if updates:
                logger.debug(f"🔄 Processing {len(updates)} updates")

            for update in updates:
                offset = update["update_id"] + 1
                try:
                    handle_message(orchestrator, update)
                except Exception as e:
                    logger.error(f"Error handling update: {e}", exc_info=True)

        except requests.exceptions.Timeout:
            continue  # Normal for long polling
        except requests.exceptions.ConnectionError:
            logger.warning("⚠️ Connection error — retrying in 5s...")
            time.sleep(5)
        except Exception as e:
            logger.error(f"Polling error: {e}", exc_info=True)
            time.sleep(5)

        time.sleep(1)


if __name__ == "__main__":
    main()
