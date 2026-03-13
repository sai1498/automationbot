"""
SQLAlchemy database models for job tracking, content caching, and session management.
Uses SQLite for zero-infrastructure deployment.
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, Float
from sqlalchemy.orm import declarative_base, sessionmaker
from config.settings import Config

logger = logging.getLogger(__name__)

Base = declarative_base()


class Job(Base):
    """Tracks every content generation job from input to publishing."""
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True)
    status = Column(String(50), default="pending", index=True)
    # Status flow: pending → processing → generated → publishing → published / failed
    input_type = Column(String(20))  # text, voice, photo, url
    input_text = Column(Text)
    content_json = Column(Text)  # Stored as JSON string
    platform_targets = Column(String(200))  # comma-separated: linkedin,instagram,community
    error_logs = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    published_at = Column(DateTime, nullable=True)

    def set_content(self, content_dict: dict):
        self.content_json = json.dumps(content_dict)

    def get_content(self) -> dict:
        return json.loads(self.content_json) if self.content_json else {}

    def __repr__(self):
        return f"<Job #{self.id} [{self.status}] user={self.user_id}>"


class ContentCache(Base):
    """Cache layer to avoid re-processing identical inputs."""
    __tablename__ = "content_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    input_hash = Column(String(64), unique=True, index=True)
    content_json = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    @staticmethod
    def hash_input(text: str) -> str:
        return hashlib.sha256(text.strip().lower().encode()).hexdigest()

    def get_content(self) -> dict:
        return json.loads(self.content_json) if self.content_json else {}


class UserSession(Base):
    """Database-backed session state — replaces in-memory pending_posts dict."""
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, unique=True, index=True)
    pending_post_json = Column(Text)  # Full post data as JSON
    stage = Column(String(20), default="preview")  # preview, edit
    job_id = Column(Integer, nullable=True)  # Link to associated Job
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def set_post(self, post_dict: dict):
        self.pending_post_json = json.dumps(post_dict)

    def get_post(self) -> dict:
        return json.loads(self.pending_post_json) if self.pending_post_json else {}


class Analytics(Base):
    """Track publishing activity and performance."""
    __tablename__ = "analytics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer)
    platform = Column(String(50))
    action = Column(String(50))  # published, failed, retry
    details = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ─── Database Engine Setup ────────────────────────────────────

def get_engine():
    """Create SQLAlchemy engine, ensuring the data directory exists."""
    db_url = Config.DATABASE_URL
    if db_url.startswith("sqlite:///"):
        # Extract path and ensure directory exists
        db_path = db_url.replace("sqlite:///", "")
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
    return create_engine(db_url, echo=False)


def init_db():
    """Create all tables if they don't exist."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info("✅ Database initialized")
    return engine


def get_session_factory():
    """Get a sessionmaker bound to the engine."""
    engine = get_engine()
    return sessionmaker(bind=engine)
