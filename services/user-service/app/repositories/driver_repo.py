from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.driver_profile import DriverProfile


class DriverRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, driver: DriverProfile) -> DriverProfile:
        self.session.add(driver)
        await self.session.flush()
        return driver

    async def get_by_user_id(self, user_id: UUID) -> DriverProfile | None:
        result = await self.session.execute(
            select(DriverProfile).where(DriverProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_by_fleet(
        self,
        fleet_id: UUID,
        offset: int = 0,
        limit: int = 20,
        is_online: bool | None = None,
        is_approved: bool | None = None,
    ) -> tuple[list[DriverProfile], int]:
        query = select(DriverProfile).where(DriverProfile.business_id == fleet_id)

        if is_online is not None:
            query = query.where(DriverProfile.is_online == is_online)
        if is_approved is not None:
            query = query.where(DriverProfile.is_approved == is_approved)

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            query.options(
                selectinload(DriverProfile.user),
                selectinload(DriverProfile.fleet),
            )
            .offset(offset)
            .limit(limit)
            .order_by(DriverProfile.created_at.desc())
        )
        return list(result.scalars().all()), total

    async def update(self, user_id: UUID, **kwargs) -> None:
        await self.session.execute(
            update(DriverProfile)
            .where(DriverProfile.user_id == user_id)
            .values(**kwargs)
        )

    async def get_available_drivers(self) -> list[DriverProfile]:
        """Get all approved, online drivers who are NOT currently on a trip."""
        result = await self.session.execute(
            select(DriverProfile)
            .where(
                DriverProfile.is_approved.is_(True),
                DriverProfile.is_online.is_(True),
                DriverProfile.is_on_trip.is_(False),
            )
            .order_by(DriverProfile.rating.desc())
        )
        return list(result.scalars().all())

    async def set_online_status(self, user_id: UUID, is_online: bool) -> None:
        await self.update(user_id, is_online=is_online)

    async def set_trip_status(self, user_id: UUID, is_on_trip: bool) -> None:
        """Update driver's trip status (called by ride events)."""
        await self.update(user_id, is_on_trip=is_on_trip)

    async def get_all_with_specialty(self) -> list[DriverProfile]:
        """Get all drivers with a specialty (caregivers)."""
        result = await self.session.execute(
            select(DriverProfile)
            .where(DriverProfile.specialty.isnot(None))
            .order_by(DriverProfile.created_at.desc())
        )
        return list(result.scalars().all())
