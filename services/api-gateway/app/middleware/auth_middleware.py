import logging

from app.config import settings
from mediride_common.auth.jwt_handler import JWTHandler
from mediride_common.auth.models import UserClaims
from mediride_common.auth.revocation import is_token_revoked

logger = logging.getLogger(__name__)

_jwt_handler = JWTHandler(
    secret_key=settings.JWT_SECRET_KEY,
    algorithm=settings.JWT_ALGORITHM,
)


def validate_jwt_and_get_claims(token: str) -> UserClaims | None:
    """Validate JWT and return user claims."""
    try:
        return _jwt_handler.decode_to_claims(token)
    except Exception as e:
        logger.warning(f"JWT validation failed: {e}")
        return None


async def token_was_revoked(token: str, claims: UserClaims) -> bool:
    """True if the user logged out, was suspended, etc. after this token was issued."""
    try:
        payload = _jwt_handler.decode_token(token)
    except Exception:
        return False
    return await is_token_revoked(claims.id, payload.iat, settings.REDIS_URL)
