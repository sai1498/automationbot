"""
Retry decorator with exponential backoff for external API calls.
"""

import time
import logging
import functools

logger = logging.getLogger(__name__)


def retry_with_backoff(max_attempts: int = 3, base_delay: float = 2.0,
                       max_delay: float = 60.0, exceptions: tuple = (Exception,)):
    """
    Decorator that retries a function with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts (including first try)
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay cap in seconds
        exceptions: Tuple of exception types to catch and retry
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(
                            f"❌ {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    logger.warning(
                        f"⚠️ {func.__name__} attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator
