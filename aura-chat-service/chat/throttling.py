"""Redis-backed fixed-window rate limiter.

Usage
-----
from chat.throttling import RateLimiter

limiter = RateLimiter()
allowed = limiter.is_allowed(f"msg:{user_id}", limit=30, window=60)
if not allowed:
    ...  # return 429

Design notes
------------
* Fixed window (not sliding) — cheap: one INCR + one EXPIRE per request.
* Fails open: if Redis is unreachable the request is allowed. This is the
  production-safe default; a Redis outage should not stop the chat service.
* The Redis connection is lazy-initialised and shared across requests via
  a module-level singleton pool.
"""

import logging
import time

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None


def _get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _client


class RateLimiter:
    """Shared, stateless rate-limiter interface."""

    def is_allowed(self, key: str, limit: int, window: int = 60) -> bool:
        """
        Return True if the action is within the rate limit, False otherwise.

        Args:
            key:    A unique string identifying the resource being rate-limited
                    (e.g. "msg:42" for user 42's messages).
            limit:  Maximum number of requests allowed in the given window.
            window: Window size in seconds (default 60 s).
        """
        if not getattr(settings, "RATE_LIMIT_ENABLED", True):
            return True

        bucket = int(time.time()) // window
        redis_key = f"rl:{key}:{bucket}"

        try:
            r = _get_client()
            pipe = r.pipeline(transaction=False)
            pipe.incr(redis_key)
            pipe.expire(redis_key, window * 2)  # TTL = 2× window → cleans up naturally
            count, _ = pipe.execute()
            return count <= limit
        except redis.RedisError as exc:
            logger.warning("Rate-limit check skipped (Redis unavailable): %s", exc)
            return True  # fail open
