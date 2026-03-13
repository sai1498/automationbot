"""
Telegram message handlers — routes updates to orchestrator methods.
"""

import logging

logger = logging.getLogger(__name__)


def handle_message(orchestrator, update: dict):
    """Route a Telegram update to the appropriate handler."""
    from database import session_store

    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]

        # Check if user is in edit mode (revision flow)
        session = session_store.get_session(chat_id)
        if session and session.get("stage") == "edit":
            text = msg.get("text", "")
            if text:
                orchestrator.process_revision(chat_id, text)
        else:
            orchestrator.process_message(msg)

    elif "callback_query" in update:
        cb = update["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        message_id = cb["message"]["message_id"]
        data = cb["data"]
        orchestrator.handle_approval(chat_id, data, message_id)
