from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_invitation import AdminInvitation
from mediride_common.schemas.enums import InvitationStatus
from mediride_common.utils import utc_now


class AdminInvitationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, invitation: AdminInvitation) -> AdminInvitation:
        self.session.add(invitation)
        await self.session.flush()
        return invitation

    async def get_by_token(self, token: str) -> AdminInvitation | None:
        result = await self.session.execute(
            select(AdminInvitation).where(AdminInvitation.token == token)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> AdminInvitation | None:
        """Get pending invitation by email."""
        result = await self.session.execute(
            select(AdminInvitation).where(
                AdminInvitation.email == email,
                AdminInvitation.status == InvitationStatus.PENDING,
            )
        )
        return result.scalar_one_or_none()

    async def list_pending(
        self, offset: int = 0, limit: int = 20
    ) -> tuple[list[AdminInvitation], int]:
        """List all pending admin invitations."""
        query = select(AdminInvitation).where(
            AdminInvitation.status == InvitationStatus.PENDING
        )
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            query.offset(offset)
            .limit(limit)
            .order_by(AdminInvitation.created_at.desc())
        )
        return list(result.scalars().all()), total

    async def mark_accepted(self, invitation_id: UUID) -> None:
        await self.session.execute(
            update(AdminInvitation)
            .where(AdminInvitation.id == invitation_id)
            .values(status=InvitationStatus.ACCEPTED, accepted_at=utc_now())
        )

    async def revoke(self, invitation_id: UUID) -> None:
        await self.session.execute(
            update(AdminInvitation)
            .where(AdminInvitation.id == invitation_id)
            .values(status=InvitationStatus.REVOKED)
        )

    async def get_by_id(self, invitation_id: UUID) -> AdminInvitation | None:
        result = await self.session.execute(
            select(AdminInvitation).where(AdminInvitation.id == invitation_id)
        )
        return result.scalar_one_or_none()
