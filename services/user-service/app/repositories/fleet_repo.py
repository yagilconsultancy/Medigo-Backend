from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fleet import Fleet


class FleetRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, fleet: Fleet) -> Fleet:
        self.session.add(fleet)
        await self.session.flush()
        return fleet

    async def get_by_id(self, fleet_id: UUID) -> Fleet | None:
        result = await self.session.execute(
            select(Fleet).where(
                Fleet.id == fleet_id, Fleet.deleted_at.is_(None)
            )
        )
        return result.scalar_one_or_none()

    async def list_all(
        self, offset: int = 0, limit: int = 20
    ) -> tuple[list[Fleet], int]:
        query = select(Fleet).where(Fleet.deleted_at.is_(None))
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            query.offset(offset).limit(limit).order_by(Fleet.created_at.desc())
        )
        return list(result.scalars().all()), total

    async def update(self, fleet_id: UUID, **kwargs) -> None:
        await self.session.execute(
            update(Fleet).where(Fleet.id == fleet_id).values(**kwargs)
        )
