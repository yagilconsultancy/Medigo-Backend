import logging

from app.config import settings
from mediride_common.auth.jwt_handler import JWTHandler
from mediride_common.auth.models import UserClaims

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
