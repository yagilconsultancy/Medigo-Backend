import logging
import secrets
from datetime import timedelta
from uuid import UUID

from app.config import settings
from app.models.business import Business
from app.models.driver_invitation import DriverInvitation
from app.repositories.business_repo import BusinessRepository
from app.repositories.invitation_repo import InvitationRepository
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher
from mediride_common.events.schemas import BusinessCreatedPayload, DriverInviteSentPayload
from mediride_common.exceptions import ConflictError, NotFoundError
from mediride_common.utils import utc_now

logger = logging.getLogger(__name__)


class BusinessService:
    def __init__(
        self,
        business_repo: BusinessRepository,
        invitation_repo: InvitationRepository,
        publisher: EventPublisher,
    ):
        self.business_repo = business_repo
        self.invitation_repo = invitation_repo
        self.publisher = publisher

    async def create_business(
        self, created_by: UUID, **kwargs
    ) -> Business:
        business = Business(onboarded_by=created_by, **kwargs)
        await self.business_repo.create(business)

        await self.publisher.publish(
            Exchanges.USERS,
            RoutingKeys.BUSINESS_CREATED,
            BusinessCreatedPayload(
                business_id=business.id,
                name=business.name,
                created_by=created_by,
            ).model_dump(mode="json"),
        )

        logger.info(f"Business created: {business.id}")
        return business

    async def get_business(self, business_id: UUID) -> Business:
        business = await self.business_repo.get_by_id(business_id)
        if not business:
            raise NotFoundError("Business not found")
        return business

    async def list_businesses(
        self, offset: int = 0, limit: int = 20
    ) -> tuple[list[Business], int]:
        return await self.business_repo.list_all(offset, limit)

    async def update_business(self, business_id: UUID, **kwargs) -> Business:
        business = await self.business_repo.get_by_id(business_id)
        if not business:
            raise NotFoundError("Business not found")
        await self.business_repo.update(business_id, **kwargs)
        return await self.business_repo.get_by_id(business_id)

    async def invite_driver(
        self, business_id: UUID, email: str, invited_by: UUID
    ) -> DriverInvitation:
        business = await self.business_repo.get_by_id(business_id)
        if not business:
            raise NotFoundError("Business not found")

        # Check for existing pending invitation
        existing = await self.invitation_repo.get_by_email_and_business(
            email, business_id
        )
        if existing:
            raise ConflictError("An invitation for this email already exists")

        token = secrets.token_urlsafe(32)
        invitation = DriverInvitation(
            business_id=business_id,
            email=email,
            invited_by=invited_by,
            token=token,
            expires_at=utc_now() + timedelta(days=settings.INVITE_TOKEN_EXPIRE_DAYS),
        )
        await self.invitation_repo.create(invitation)

        # Publish event for notification service
        await self.publisher.publish(
            Exchanges.AUTH,
            RoutingKeys.DRIVER_INVITE_SENT,
            DriverInviteSentPayload(
                invitation_id=invitation.id,
                business_id=business_id,
                business_name=business.name,
                email=email,
                invite_token=token,
            ).model_dump(mode="json"),
        )

        logger.info(f"Driver invited: {email} for business {business_id}")
        return invitation

    async def list_invitations(
        self, business_id: UUID, offset: int = 0, limit: int = 20
    ) -> tuple[list[DriverInvitation], int]:
        return await self.invitation_repo.list_by_business(business_id, offset, limit)

    async def revoke_invitation(
        self, business_id: UUID, invitation_id: UUID
    ) -> None:
        invitation = await self.invitation_repo.get_by_token("")
        # Get by ID instead
        from sqlalchemy import select
        # Simple revoke
        await self.invitation_repo.revoke(invitation_id)
