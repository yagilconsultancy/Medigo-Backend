import logging
import secrets
from datetime import timedelta
from uuid import UUID

from app.config import settings
from app.models.fleet import Fleet
from app.models.driver_invitation import DriverInvitation
from app.repositories.fleet_repo import FleetRepository
from app.repositories.invitation_repo import InvitationRepository
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher
from mediride_common.events.schemas import FleetCreatedPayload, DriverInviteSentPayload
from mediride_common.exceptions import ConflictError, NotFoundError
from mediride_common.utils import utc_now

logger = logging.getLogger(__name__)


class FleetService:
    def __init__(
        self,
        fleet_repo: FleetRepository,
        invitation_repo: InvitationRepository,
        publisher: EventPublisher,
    ):
        self.fleet_repo = fleet_repo
        self.invitation_repo = invitation_repo
        self.publisher = publisher

    async def create_fleet(
        self, created_by: UUID, **kwargs
    ) -> Fleet:
        fleet = Fleet(onboarded_by=created_by, **kwargs)
        await self.fleet_repo.create(fleet)

        await self.publisher.publish(
            Exchanges.USERS,
            RoutingKeys.FLEET_CREATED,
            FleetCreatedPayload(
                fleet_id=fleet.id,
                name=fleet.name,
                created_by=created_by,
            ).model_dump(mode="json"),
        )

        logger.info(f"Fleet created: {fleet.id}")
        return fleet

    async def get_fleet(self, fleet_id: UUID) -> Fleet:
        fleet = await self.fleet_repo.get_by_id(fleet_id)
        if not fleet:
            raise NotFoundError("Fleet not found")
        return fleet

    async def list_fleets(
        self, offset: int = 0, limit: int = 20
    ) -> tuple[list[Fleet], int]:
        return await self.fleet_repo.list_all(offset, limit)

    async def update_fleet(self, fleet_id: UUID, **kwargs) -> Fleet:
        fleet = await self.fleet_repo.get_by_id(fleet_id)
        if not fleet:
            raise NotFoundError("Fleet not found")
        await self.fleet_repo.update(fleet_id, **kwargs)
        return await self.fleet_repo.get_by_id(fleet_id)

    async def invite_driver(
        self, fleet_id: UUID, email: str, invited_by: UUID
    ) -> DriverInvitation:
        fleet = await self.fleet_repo.get_by_id(fleet_id)
        if not fleet:
            raise NotFoundError("Fleet not found")

        # Check for existing pending invitation
        existing = await self.invitation_repo.get_by_email_and_fleet(
            email, fleet_id
        )
        if existing:
            raise ConflictError("An invitation for this email already exists")

        token = secrets.token_urlsafe(32)
        invitation = DriverInvitation(
            business_id=fleet_id,
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
                business_id=fleet_id,
                fleet_name=fleet.name,
                email=email,
                invite_token=token,
            ).model_dump(mode="json"),
        )

        logger.info(f"Driver invited: {email} for fleet {fleet_id}")
        return invitation

    async def list_invitations(
        self, fleet_id: UUID, offset: int = 0, limit: int = 20
    ) -> tuple[list[DriverInvitation], int]:
        return await self.invitation_repo.list_by_fleet(fleet_id, offset, limit)

    async def revoke_invitation(
        self, fleet_id: UUID, invitation_id: UUID
    ) -> None:
        await self.invitation_repo.revoke(invitation_id)
