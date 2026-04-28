from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.guest_booking_session import GuestBookingSession


class GuestBookingSessionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, guest_session: GuestBookingSession) -> GuestBookingSession:
        self.session.add(guest_session)
        await self.session.flush()
        return guest_session

    async def get_by_id(self, session_id: UUID) -> GuestBookingSession | None:
        result = await self.session.execute(
            select(GuestBookingSession).where(GuestBookingSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def update(self, session_id: UUID, **kwargs) -> None:
        await self.session.execute(
            update(GuestBookingSession)
            .where(GuestBookingSession.id == session_id)
            .values(**kwargs)
        )
