from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.saved_location import SavedLocation


class SavedLocationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, location: SavedLocation) -> SavedLocation:
        self.session.add(location)
        await self.session.flush()
        await self.session.refresh(location)
        return location

    async def get_by_id(self, location_id: UUID) -> SavedLocation | None:
        result = await self.session.execute(
            select(SavedLocation).where(SavedLocation.id == location_id)
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: UUID) -> list[SavedLocation]:
        result = await self.session.execute(
            select(SavedLocation)
            .where(SavedLocation.user_id == user_id)
            .order_by(SavedLocation.sort_order.asc(), SavedLocation.created_at.asc())
        )
        return list(result.scalars().all())

    async def count_by_user(self, user_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count(SavedLocation.id)).where(
                SavedLocation.user_id == user_id
            )
        )
        return result.scalar() or 0

    async def get_by_user_and_type(
        self, user_id: UUID, location_type: str
    ) -> SavedLocation | None:
        result = await self.session.execute(
            select(SavedLocation).where(
                SavedLocation.user_id == user_id,
                SavedLocation.location_type == location_type,
            )
        )
        return result.scalar_one_or_none()

    async def update(self, location_id: UUID, **kwargs) -> None:
        await self.session.execute(
            update(SavedLocation)
            .where(SavedLocation.id == location_id)
            .values(**kwargs)
        )

    async def delete(self, location_id: UUID) -> None:
        await self.session.execute(
            delete(SavedLocation).where(SavedLocation.id == location_id)
        )
        await self.session.flush()

    async def clear_default(self, user_id: UUID) -> None:
        await self.session.execute(
            update(SavedLocation)
            .where(
                SavedLocation.user_id == user_id,
                SavedLocation.is_default == True,  # noqa: E712
            )
            .values(is_default=False)
        )

    async def update_sort_orders(self, user_id: UUID, id_order: list[UUID]) -> None:
        for idx, loc_id in enumerate(id_order):
            await self.session.execute(
                update(SavedLocation)
                .where(SavedLocation.id == loc_id, SavedLocation.user_id == user_id)
                .values(sort_order=idx)
            )
