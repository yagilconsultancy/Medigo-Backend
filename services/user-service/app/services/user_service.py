import logging
from datetime import datetime, timezone
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
        first_name: str | None,
        last_name: str | None,
        role: str,
        business_id: UUID | None = None,
        is_guest: bool = False,
    ) -> User:
        """Create initial user profile from auth registration event."""
        user = User(
            id=user_id,
            email=email,
            phone=phone,
            first_name=first_name or "",
            last_name=last_name or "",
            role=role,
            business_id=business_id,
            is_guest=is_guest,
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

    async def update_consent(
        self,
        user_id: UUID,
        consent_emergency_services: bool,
        consent_privacy_policy: bool,
        consent_terms_of_service: bool,
        consent_data_location: bool,
    ) -> User:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User profile not found")
        await self.user_repo.update(
            user_id,
            consent_emergency_services=consent_emergency_services,
            consent_privacy_policy=consent_privacy_policy,
            consent_terms_of_service=consent_terms_of_service,
            consent_data_location=consent_data_location,
            consent_accepted_at=datetime.now(timezone.utc),
        )
        return await self.user_repo.get_by_id(user_id)

    async def update_onboarding_step(self, user_id: UUID, step: int) -> User:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User profile not found")
        update_data = {"onboarding_step": step}
        if step > 5:
            update_data["onboarding_completed"] = True
            update_data["onboarding_step"] = 5
        await self.user_repo.update(user_id, **update_data)
        return await self.user_repo.get_by_id(user_id)

    def get_onboarding_status(self, user: User) -> dict:
        steps = [
            {
                "step": 1,
                "name": "Account Created",
                "completed": bool(user.email or user.phone),
            },
            {
                "step": 2,
                "name": "Personal Information",
                "completed": bool(user.first_name and user.last_name),
            },
            {
                "step": 3,
                "name": "Review & Accept",
                "completed": bool(
                    user.consent_privacy_policy and user.consent_terms_of_service
                ),
            },
            {
                "step": 4,
                "name": "Payment Method",
                "completed": user.onboarding_step >= 4 and user.onboarding_completed,
            },
            {
                "step": 5,
                "name": "Agreement & Privacy",
                "completed": bool(
                    user.consent_data_location and user.consent_emergency_services
                ),
            },
        ]
        return {
            "current_step": user.onboarding_step,
            "total_steps": 5,
            "completed": user.onboarding_completed,
            "steps": steps,
        }

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
