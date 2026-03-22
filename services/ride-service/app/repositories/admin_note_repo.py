from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_note import AdminNote


class AdminNoteRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, note: AdminNote) -> AdminNote:
        self.session.add(note)
        await self.session.flush()
        return note

    async def get_by_ride(self, ride_id: UUID) -> list[AdminNote]:
        result = await self.session.execute(
            select(AdminNote)
            .where(AdminNote.ride_id == ride_id)
            .order_by(AdminNote.created_at.asc())
        )
        return list(result.scalars().all())
