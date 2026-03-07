from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recurring_ride import RecurringRide


class RecurringRideRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, recurring_ride: RecurringRide) -> RecurringRide:
        self.session.add(recurring_ride)
        await self.session.flush()
        return recurring_ride

    async def get_by_id(self, rec_id: UUID) -> RecurringRide | None:
        result = await self.session.execute(
            select(RecurringRide).where(RecurringRide.id == rec_id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_rider(self, rider_id: UUID) -> list[RecurringRide]:
        result = await self.session.execute(
            select(RecurringRide).where(
                RecurringRide.rider_id == rider_id,
                RecurringRide.is_active.is_(True),
            ).order_by(RecurringRide.created_at.desc())
        )
        return list(result.scalars().all())

    async def deactivate(self, rec_id: UUID) -> None:
        await self.session.execute(
            update(RecurringRide)
            .where(RecurringRide.id == rec_id)
            .values(is_active=False)
        )
