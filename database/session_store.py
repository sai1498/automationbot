"""
Database-backed session store — replaces the in-memory pending_posts dictionary.
Survives server restarts and supports horizontal scaling.
"""

import json
import logging
from database.models import UserSession, get_session_factory

logger = logging.getLogger(__name__)

_SessionFactory = None


def _get_factory():
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = get_session_factory()
    return _SessionFactory


def get_session(chat_id: int) -> dict | None:
    """Retrieve a pending post session for a chat ID."""
    factory = _get_factory()
    with factory() as db:
        session = db.query(UserSession).filter_by(chat_id=chat_id).first()
        if session:
            post = session.get_post()
            post["stage"] = session.stage
            post["job_id"] = session.job_id
            return post
    return None


def save_session(chat_id: int, post_data: dict, stage: str = "preview", job_id: int = None):
    """Save or update a pending post session."""
    factory = _get_factory()
    with factory() as db:
        session = db.query(UserSession).filter_by(chat_id=chat_id).first()
        if session:
            session.set_post(post_data)
            session.stage = stage
            if job_id is not None:
                session.job_id = job_id
        else:
            session = UserSession(chat_id=chat_id, stage=stage, job_id=job_id)
            session.set_post(post_data)
            db.add(session)
        db.commit()
        logger.debug(f"Session saved for chat_id={chat_id}")


def update_stage(chat_id: int, stage: str):
    """Update only the stage of an existing session."""
    factory = _get_factory()
    with factory() as db:
        session = db.query(UserSession).filter_by(chat_id=chat_id).first()
        if session:
            session.stage = stage
            db.commit()


def delete_session(chat_id: int):
    """Delete a pending post session."""
    factory = _get_factory()
    with factory() as db:
        session = db.query(UserSession).filter_by(chat_id=chat_id).first()
        if session:
            db.delete(session)
            db.commit()
            logger.debug(f"Session deleted for chat_id={chat_id}")
