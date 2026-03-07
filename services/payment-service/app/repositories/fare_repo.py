from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fare_breakdown import FareBreakdown


class FareBreakdownRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, breakdown: FareBreakdown) -> FareBreakdown:
        self.session.add(breakdown)
        await self.session.flush()
        return breakdown

    async def get_by_ride_id(self, ride_id: UUID) -> FareBreakdown | None:
        result = await self.session.execute(
            select(FareBreakdown).where(FareBreakdown.ride_id == ride_id)
        )
        return result.scalar_one_or_none()
