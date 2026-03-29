from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, Request

from mediride_common.auth.models import UserClaims
from mediride_common.exceptions import AuthenticationError, AuthorizationError
from mediride_common.schemas.enums import UserRole


async def get_current_user(request: Request) -> UserClaims:
    """Extract user claims from headers set by the API gateway.

    The gateway validates the JWT and sets X-User-* headers before
    proxying to downstream services.
    """
    user_id = request.headers.get("X-User-ID")
    user_role = request.headers.get("X-User-Role")

    if not user_id or not user_role:
        raise AuthenticationError("Missing authentication headers")

    try:
        role = UserRole(user_role)
    except ValueError:
        raise AuthenticationError(f"Invalid role: {user_role}")

    business_id_str = request.headers.get("X-Business-ID")
    business_id = UUID(business_id_str) if business_id_str else None
    email = request.headers.get("X-User-Email")

    return UserClaims(
        id=UUID(user_id),
        role=role,
        business_id=business_id,
        email=email,
    )


def require_role(allowed_roles: list[UserRole]) -> Callable:
    """Dependency factory that restricts access to specific roles."""

    async def _check(user: UserClaims = Depends(get_current_user)) -> UserClaims:
        if user.role not in allowed_roles:
            raise AuthorizationError(
                f"Role '{user.role}' is not authorized for this resource"
            )
        return user

    return _check


