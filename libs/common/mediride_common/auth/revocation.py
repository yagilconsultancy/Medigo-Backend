"""Cut off access tokens that are already in circulation.

Access tokens are signed and checked by the gateway without a database, so a
token stays valid until it expires even after the user logged out, reset their
password, was suspended or deleted. To close that gap we keep one marker per
user in Redis: "tokens issued before time T are no longer valid". The gateway
reads it on every request.

Both functions fail open: if Redis is unreachable the request goes through as
it did before this existed, so a Redis outage can never lock everyone out.
"""

import logging
import time

logger = logging.getLogger(__name__)

KEY_PREFIX = "auth:revoked_before:"
# Longer than any access token lifetime (admin sessions can be extended).
MARKER_TTL_SECONDS = 24 * 60 * 60

_clients: dict = {}


def _client(redis_url: str):
    client = _clients.get(redis_url)
    if client is None:
        import redis.asyncio as redis

        client = redis.from_url(redis_url, decode_responses=True)
        _clients[redis_url] = client
    return client


async def revoke_user_tokens(user_id, redis_url: str) -> None:
    """Invalidate every access token issued to this user up to now."""
    try:
        # +1 so a token issued in the same second as the revoke is covered.
        marker = int(time.time()) + 1
        await _client(redis_url).set(
            f"{KEY_PREFIX}{user_id}", marker, ex=MARKER_TTL_SECONDS
        )
    except Exception:
        logger.warning("Could not record token revocation", exc_info=True)


async def is_token_revoked(user_id, issued_at: int | None, redis_url: str) -> bool:
    """True if the token was issued before the user's revocation marker."""
    if issued_at is None:
        return False
    try:
        value = await _client(redis_url).get(f"{KEY_PREFIX}{user_id}")
        return value is not None and int(issued_at) < int(value)
    except Exception:
        logger.warning("Could not check token revocation", exc_info=True)
        return False


async def claim_single_use(key: str, redis_url: str, ttl_seconds: int) -> bool:
    """Return True the first time `key` is seen, False on any later use.

    Used for one-time links. Fails open (returns True) if Redis is unreachable.
    """
    try:
        created = await _client(redis_url).set(
            f"auth:single_use:{key}", "1", ex=ttl_seconds, nx=True
        )
        return bool(created)
    except Exception:
        logger.warning("Could not record single-use claim", exc_info=True)
        return True
