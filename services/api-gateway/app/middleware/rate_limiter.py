import logging
import time

import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _redis_client
    if not _redis_client:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


async def check_rate_limit(
    key: str,
    max_requests: int | None = None,
    window_seconds: int | None = None,
) -> bool:
    """Check if request is within rate limit using sliding window.

    Returns True if request is allowed, False if rate limited.
    """
    if max_requests is None:
        max_requests = settings.RATE_LIMIT_REQUESTS
    if window_seconds is None:
        window_seconds = settings.RATE_LIMIT_WINDOW

    try:
        r = await get_redis()
        now = time.time()
        pipeline = r.pipeline()

        # Remove expired entries
        pipeline.zremrangebyscore(key, 0, now - window_seconds)
        # Add current request
        pipeline.zadd(key, {str(now): now})
        # Count requests in window
        pipeline.zcard(key)
        # Set TTL
        pipeline.expire(key, window_seconds)

        results = await pipeline.execute()
        request_count = results[2]

        return request_count <= max_requests
    except Exception as e:
        logger.warning(f"Rate limiting error: {e}")
        # Fail open: allow request if Redis is down
        return True
