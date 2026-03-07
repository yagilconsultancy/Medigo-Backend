from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.location_history import LocationHistory


class LocationHistoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, entry: LocationHistory) -> LocationHistory:
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def get_by_session(
        self, session_id: UUID, offset: int = 0, limit: int = 1000
    ) -> tuple[list[LocationHistory], int]:
        count_result = await self.session.execute(
            select(func.count()).where(LocationHistory.session_id == session_id)
        )
        total = count_result.scalar() or 0

        result = await self.session.execute(
            select(LocationHistory)
            .where(LocationHistory.session_id == session_id)
            .order_by(LocationHistory.recorded_at.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total
