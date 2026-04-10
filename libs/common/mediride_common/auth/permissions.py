"""Module-based permission enforcement and role hierarchy for admin users."""
import logging
from typing import Callable
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from mediride_common.auth.dependencies import get_current_user
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole

logger = logging.getLogger(__name__)

# Role hierarchy: admin > business > driver > rider
ROLE_HIERARCHY = {
    UserRole.ADMIN: 4,
    UserRole.BUSINESS: 3,
    UserRole.DRIVER: 2,
    UserRole.RIDER: 1,
}


def has_higher_or_equal_role(user_role: UserRole, required_role: UserRole) -> bool:
    return ROLE_HIERARCHY.get(user_role, 0) >= ROLE_HIERARCHY.get(required_role, 0)


def require_module_access(
    module_name: str, session_dependency: Callable[[], AsyncSession] | None = None
) -> Callable:
    """
    Dependency that checks if the current admin user has access to a specific module.

    This version is for user-service which has the admin_roles tables locally.

    Usage in user-service endpoints:
        from app.dependencies import get_db

        @router.get("/admin/drivers")
        async def list_drivers(
            _admin: UserClaims = Depends(require_module_access("driver_management", get_db)),
        ):
            ...

    Args:
        module_name: The module to check access for (e.g., "driver_management")
        session_dependency: Optional database session dependency (for user-service)

    Returns:
        Dependency function that returns UserClaims if authorized

    Raises:
        HTTPException: 403 if user doesn't have access to the module
    """

    async def _check_access(
        user: UserClaims = Depends(get_current_user),
        session: AsyncSession = Depends(session_dependency)
        if session_dependency
        else None,
    ) -> UserClaims:
        # Only apply module checks to ADMIN users
        if user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=403,
                detail="Module access control applies only to admin users",
            )

        # If no session provided, skip database check (for services without tables)
        if session is None:
            logger.warning(
                f"Module access check for {module_name} skipped - no database session"
            )
            return user

        # Check if user has access via their role assignments
        query = text(
            """
            SELECT 1
            FROM admin_role_assignments ara
            JOIN module_permissions mp ON ara.role_id = mp.role_id
            WHERE ara.user_id = :user_id
              AND mp.module_name = :module_name
              AND mp.can_access = true
            LIMIT 1
            """
        )

        result = await session.execute(
            query.bindparams(user_id=user.id, module_name=module_name)
        )

        has_access = result.scalar_one_or_none() is not None

        if not has_access:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied: You don't have permission to access '{module_name}' module",
            )

        return user

    return _check_access


class ModuleAccessChecker:
    """
    Helper class for services that don't have admin_roles tables locally.
    These services should call user-service to check permissions via HTTP.
    """

    def __init__(self, user_service_url: str, internal_service_token: str):
        """
        Initialize the checker.

        Args:
            user_service_url: Base URL of user-service (e.g., "http://user-service:8002")
            internal_service_token: Secret token for X-Internal-Service header
        """
        self.user_service_url = user_service_url
        self.internal_service_token = internal_service_token

    async def check_access(self, user_id: UUID, module_name: str) -> bool:
        """
        Check module access by calling user-service internal endpoint.

        Args:
            user_id: User UUID
            module_name: Module to check

        Returns:
            True if user has access, False otherwise
        """
        import httpx

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.user_service_url}/internal/check-module-access",
                    json={"user_id": str(user_id), "module_name": module_name},
                    headers={"X-Internal-Service": self.internal_service_token},
                    timeout=5.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("has_access", False)
                return False
            except Exception as e:
                logger.error(f"Failed to check module access: {e}")
                # Fail closed (deny access) on error
                return False

    def require_module_access(self, module_name: str) -> Callable:
        """
        Dependency factory that uses HTTP to check permissions.

        Usage in other services (ride-service, payment-service, etc.):
            from mediride_common.auth.permissions import ModuleAccessChecker
            from app.config import settings

            checker = ModuleAccessChecker(
                settings.USER_SERVICE_URL,
                settings.INTERNAL_SERVICE_TOKEN
            )

            @router.get("/admin/something")
            async def endpoint(
                _admin: UserClaims = Depends(checker.require_module_access("some_module"))
            ):
                ...
        """

        async def _check_access(
            user: UserClaims = Depends(get_current_user),
        ) -> UserClaims:
            if user.role != UserRole.ADMIN:
                raise HTTPException(
                    status_code=403,
                    detail="Module access control applies only to admin users",
                )

            has_access = await self.check_access(
                user_id=user.id, module_name=module_name
            )

            if not has_access:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied: You don't have permission to access '{module_name}' module",
                )

            return user

        return _check_access
