from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ride_status_log import RideStatusLog


class StatusLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, log: RideStatusLog) -> RideStatusLog:
        self.session.add(log)
        await self.session.flush()
        return log

    async def get_by_ride(self, ride_id: UUID) -> list[RideStatusLog]:
        result = await self.session.execute(
            select(RideStatusLog)
            .where(RideStatusLog.ride_id == ride_id)
            .order_by(RideStatusLog.timestamp.asc())
        )
        return list(result.scalars().all())
