from __future__ import annotations

import logging
from functools import lru_cache

from src.config import get_settings

logger = logging.getLogger(__name__)

try:
    from pyrate_limiter import Duration, Limiter, RequestRate
    from pyrate_limiter.buckets import RedisBucket

    _HAS_REDIS = True
except ImportError:
    _HAS_REDIS = False

try:
    from pyrate_limiter import Duration, Limiter, RequestRate
    from pyrate_limiter.buckets import InMemoryBucket

    _HAS_MEMORY = True
except ImportError:
    _HAS_MEMORY = False


def _get_rates():
    settings = get_settings()
    return [
        RequestRate(settings.rate_limit.requests_per_minute, Duration.MINUTE),
        RequestRate(settings.rate_limit.requests_per_hour, Duration.HOUR),
    ]


@lru_cache(maxsize=1)
def create_limiter():
    rates = _get_rates()

    if _HAS_REDIS:
        try:
            import redis

            settings = get_settings()
            redis_client = redis.from_url(settings.redis.url)
            bucket = RedisBucket(init_rates=rates, redis=redis_client)
            return Limiter(bucket)
        except Exception:
            logger.warning("Redis unavailable for rate limiting, falling back to in-memory")

    if _HAS_MEMORY:
        try:
            bucket = InMemoryBucket(init_rates=rates)
            return Limiter(bucket)
        except Exception:
            logger.warning("Failed to create in-memory rate limiter")

    logger.warning("Rate limiting disabled (no backend available)")
    return None


def check_rate_limit(limiter, user_id: str) -> bool:
    if limiter is None:
        return True
    try:
        limiter.try_acquire(user_id)
        return True
    except Exception:
        return False


_limiter = None


def get_limiter():
    global _limiter
    if _limiter is None:
        _limiter = create_limiter()
    return _limiter
