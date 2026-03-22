from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def list_by_business(
        self,
        business_id: UUID,
        offset: int = 0,
        limit: int = 20,
        is_online: bool | None = None,
        is_approved: bool | None = None,
    ) -> tuple[list[DriverProfile], int]:
        query = select(DriverProfile).where(DriverProfile.business_id == business_id)

        if is_online is not None:
            query = query.where(DriverProfile.is_online == is_online)
        if is_approved is not None:
            query = query.where(DriverProfile.is_approved == is_approved)

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            query.offset(offset).limit(limit).order_by(DriverProfile.created_at.desc())
        )
        return list(result.scalars().all()), total

    async def update(self, user_id: UUID, **kwargs) -> None:
        await self.session.execute(
            update(DriverProfile)
            .where(DriverProfile.user_id == user_id)
            .values(**kwargs)
        )

    async def get_available_drivers(self) -> list[DriverProfile]:
        """Get all approved drivers for admin assignment."""
        result = await self.session.execute(
            select(DriverProfile)
            .where(DriverProfile.is_approved.is_(True))
            .order_by(DriverProfile.rating.desc())
        )
        return list(result.scalars().all())

    async def set_online_status(self, user_id: UUID, is_online: bool) -> None:
        await self.update(user_id, is_online=is_online)
