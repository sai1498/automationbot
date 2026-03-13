"""
System tests for the professional architecture.
Tests config, security, database, and core components.

Run: python -m pytest tests/test_system.py -v
"""

import os
import sys
import time
import json
import hashlib
import tempfile

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment
os.environ.setdefault("TELEGRAM_TOKEN", "test_token_12345")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_key")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ALLOWED_USERS", "111,222,333")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "5")

import pytest


# ─── Config Tests ────────────────────────────────────────────

class TestConfig:
    def test_config_loads(self):
        from config.settings import Config
        assert Config.TELEGRAM_TOKEN == "test_token_12345"
        assert Config.GOOGLE_API_KEY == "test_google_key"

    def test_config_defaults(self):
        from config.settings import Config
        assert Config.RATE_LIMIT_PER_MINUTE == 5
        assert Config.LOG_LEVEL == "INFO"

    def test_allowed_users_parsing(self):
        from config.settings import Config
        Config._parse_allowed_users()
        assert 111 in Config.ALLOWED_USERS
        assert 222 in Config.ALLOWED_USERS
        assert 333 in Config.ALLOWED_USERS


# ─── Security Tests ────────────────────────────────────────────

class TestAuth:
    def test_user_allowed(self):
        from config.settings import Config
        Config._parse_allowed_users()
        from security.auth import is_user_allowed
        assert is_user_allowed(111) == True
        assert is_user_allowed(999) == False

    def test_url_sanitization_blocks_file(self):
        from security.auth import sanitize_url
        safe, reason = sanitize_url("file:///etc/passwd")
        assert safe == False
        assert "scheme" in reason.lower()

    def test_url_sanitization_blocks_localhost(self):
        from security.auth import sanitize_url
        safe, reason = sanitize_url("http://localhost/admin")
        assert safe == False
        assert "host" in reason.lower()

    def test_url_sanitization_blocks_private_ip(self):
        from security.auth import sanitize_url
        safe, reason = sanitize_url("http://192.168.1.1/admin")
        assert safe == False

    def test_url_sanitization_allows_valid(self):
        from security.auth import sanitize_url
        safe, reason = sanitize_url("https://www.example.com/page")
        assert safe == True

    def test_text_sanitization(self):
        from security.auth import sanitize_text_input
        result = sanitize_text_input("hello\x00world", max_length=5)
        assert result == "hello"
        assert "\x00" not in result


class TestRateLimiter:
    def test_allows_within_limit(self):
        from security.rate_limit import RateLimiter
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        assert limiter.check(1)[0] == True
        assert limiter.check(1)[0] == True
        assert limiter.check(1)[0] == True

    def test_blocks_over_limit(self):
        from security.rate_limit import RateLimiter
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.check(1)
        limiter.check(1)
        allowed, remaining = limiter.check(1)
        assert allowed == False
        assert remaining == 0

    def test_separate_users(self):
        from security.rate_limit import RateLimiter
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        assert limiter.check(1)[0] == True
        assert limiter.check(2)[0] == True
        assert limiter.check(1)[0] == False  # User 1 over limit
        assert limiter.check(2)[0] == False  # User 2 over limit

    def test_cleanup(self):
        from security.rate_limit import RateLimiter
        limiter = RateLimiter(max_requests=5, window_seconds=1)
        limiter.check(1)
        limiter.check(2)
        time.sleep(3)  # Wait for window to expire
        limiter.cleanup()
        # After cleanup, expired entries should be removed
        assert 1 not in limiter._requests or len(limiter._requests[1]) == 0


# ─── Database Tests ────────────────────────────────────────────

class TestDatabase:
    @pytest.fixture(autouse=True)
    def setup_db(self):
        """Create fresh in-memory database for each test."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database.models import Base, Job, ContentCache, UserSession, Analytics

        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def test_create_job(self):
        from database.models import Job
        with self.Session() as db:
            job = Job(user_id=123, status="pending", input_type="text", input_text="test news")
            db.add(job)
            db.commit()
            assert job.id is not None
            assert job.status == "pending"

    def test_job_content_json(self):
        from database.models import Job
        with self.Session() as db:
            job = Job(user_id=123, status="generated")
            job.set_content({"linkedin_post": "Hello", "community_post": "Discussion"})
            db.add(job)
            db.commit()

            loaded = db.query(Job).first()
            content = loaded.get_content()
            assert content["linkedin_post"] == "Hello"

    def test_content_cache(self):
        from database.models import ContentCache
        with self.Session() as db:
            hash_val = ContentCache.hash_input("test input")
            cache = ContentCache(input_hash=hash_val, content_json='{"test": true}')
            db.add(cache)
            db.commit()

            cached = db.query(ContentCache).filter_by(input_hash=hash_val).first()
            assert cached is not None
            assert cached.get_content()["test"] == True

    def test_user_session(self):
        from database.models import UserSession
        with self.Session() as db:
            session = UserSession(chat_id=12345, stage="preview")
            session.set_post({"content": {"test": True}, "platforms": {"linkedin": True}})
            db.add(session)
            db.commit()

            loaded = db.query(UserSession).filter_by(chat_id=12345).first()
            post = loaded.get_post()
            assert post["content"]["test"] == True
            assert loaded.stage == "preview"


# ─── Retry Tests ────────────────────────────────────────────

class TestRetry:
    def test_succeeds_first_try(self):
        from core.retry import retry_with_backoff

        @retry_with_backoff(max_attempts=3, base_delay=0.01)
        def good_fn():
            return "success"

        assert good_fn() == "success"

    def test_retries_then_succeeds(self):
        from core.retry import retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay=0.01)
        def flaky_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("temporary error")
            return "success"

        assert flaky_fn() == "success"
        assert call_count == 3

    def test_fails_after_max_attempts(self):
        from core.retry import retry_with_backoff

        @retry_with_backoff(max_attempts=2, base_delay=0.01)
        def bad_fn():
            raise RuntimeError("permanent error")

        with pytest.raises(RuntimeError):
            bad_fn()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
