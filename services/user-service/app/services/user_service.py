import logging
from uuid import UUID

from app.models.user import User
from app.repositories.user_repo import UserRepository
from mediride_common.exceptions import AuthorizationError, NotFoundError
from mediride_common.schemas.enums import UserRole

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def create_profile_from_registration(
        self,
        user_id: UUID,
        email: str | None,
        phone: str | None,
        role: str,
        business_id: UUID | None = None,
    ) -> User:
        """Create initial user profile from auth registration event."""
        user = User(
            id=user_id,
            email=email,
            phone=phone,
            first_name="",
            last_name="",
            role=role,
            business_id=business_id,
        )
        await self.user_repo.create(user)
        logger.info(f"Created profile for user {user_id}")
        return user

    async def get_profile(self, user_id: UUID) -> User:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User profile not found")
        return user

    async def update_profile(self, user_id: UUID, **kwargs) -> User:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User profile not found")
        await self.user_repo.update(user_id, **kwargs)
        return await self.user_repo.get_by_id(user_id)

    async def list_users(
        self,
        role: str | None = None,
        offset: int = 0,
        limit: int = 20,
        business_id: UUID | None = None,
        requester_role: UserRole = UserRole.ADMIN,
        requester_business_id: UUID | None = None,
    ) -> tuple[list[User], int]:
        # Business users can only see their own business users
        if requester_role == UserRole.BUSINESS:
            business_id = requester_business_id
        return await self.user_repo.list_by_role(
            role=role or "rider", offset=offset, limit=limit, business_id=business_id
        )
