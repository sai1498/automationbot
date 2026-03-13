"""
Per-user sliding window rate limiter.
No external dependencies — uses in-memory tracking with auto-cleanup.
"""

import time
import threading
import logging
from config.settings import Config

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Sliding window rate limiter.
    Tracks request timestamps per user and enforces a max-requests-per-minute limit.
    Thread-safe.
    """

    def __init__(self, max_requests: int = None, window_seconds: int = 60):
        self.max_requests = max_requests or Config.RATE_LIMIT_PER_MINUTE
        self.window_seconds = window_seconds
        self._requests: dict[int, list[float]] = {}  # {user_id: [timestamp, ...]}
        self._lock = threading.Lock()

    def check(self, user_id: int) -> tuple[bool, int]:
        """
        Check if a user is within rate limits.
        Returns (allowed: bool, remaining: int).
        """
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            # Initialize if new user
            if user_id not in self._requests:
                self._requests[user_id] = []

            # Purge expired timestamps
            self._requests[user_id] = [
                ts for ts in self._requests[user_id] if ts > cutoff
            ]

            current_count = len(self._requests[user_id])
            remaining = self.max_requests - current_count

            if current_count >= self.max_requests:
                logger.warning(f"🛑 Rate limit hit for user {user_id}: {current_count}/{self.max_requests}")
                return False, 0

            # Record this request
            self._requests[user_id].append(now)
            return True, remaining - 1

    def cleanup(self):
        """Remove entries for users with no recent activity."""
        now = time.time()
        cutoff = now - self.window_seconds * 2  # Keep 2x window for safety

        with self._lock:
            expired_users = [
                uid for uid, timestamps in self._requests.items()
                if not timestamps or max(timestamps) < cutoff
            ]
            for uid in expired_users:
                del self._requests[uid]

            if expired_users:
                logger.debug(f"Cleaned up rate limit data for {len(expired_users)} users")


# Global singleton
rate_limiter = RateLimiter()
