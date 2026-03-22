from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.driver_invitation import DriverInvitation
from mediride_common.schemas.enums import InvitationStatus
from mediride_common.utils import utc_now


class InvitationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, invitation: DriverInvitation) -> DriverInvitation:
        self.session.add(invitation)
        await self.session.flush()
        return invitation

    async def get_by_token(self, token: str) -> DriverInvitation | None:
        result = await self.session.execute(
            select(DriverInvitation).where(DriverInvitation.token == token)
        )
        return result.scalar_one_or_none()

    async def get_by_email_and_business(
        self, email: str, business_id: UUID
    ) -> DriverInvitation | None:
        result = await self.session.execute(
            select(DriverInvitation).where(
                DriverInvitation.email == email,
                DriverInvitation.business_id == business_id,
                DriverInvitation.status == InvitationStatus.PENDING,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_business(
        self, business_id: UUID, offset: int = 0, limit: int = 20
    ) -> tuple[list[DriverInvitation], int]:
        query = select(DriverInvitation).where(
            DriverInvitation.business_id == business_id
        )
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            query.offset(offset)
            .limit(limit)
            .order_by(DriverInvitation.created_at.desc())
        )
        return list(result.scalars().all()), total

    async def mark_accepted(self, invitation_id: UUID) -> None:
        await self.session.execute(
            update(DriverInvitation)
            .where(DriverInvitation.id == invitation_id)
            .values(status=InvitationStatus.ACCEPTED, accepted_at=utc_now())
        )

    async def revoke(self, invitation_id: UUID) -> None:
        await self.session.execute(
            update(DriverInvitation)
            .where(DriverInvitation.id == invitation_id)
            .values(status=InvitationStatus.REVOKED)
        )
