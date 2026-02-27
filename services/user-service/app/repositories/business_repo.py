from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business


class BusinessRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, business: Business) -> Business:
        self.session.add(business)
        await self.session.flush()
        return business

    async def get_by_id(self, business_id: UUID) -> Business | None:
        result = await self.session.execute(
            select(Business).where(
                Business.id == business_id, Business.deleted_at.is_(None)
            )
        )
        return result.scalar_one_or_none()

    async def list_all(
        self, offset: int = 0, limit: int = 20
    ) -> tuple[list[Business], int]:
        query = select(Business).where(Business.deleted_at.is_(None))
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            query.offset(offset).limit(limit).order_by(Business.created_at.desc())
        )
        return list(result.scalars().all()), total

    async def update(self, business_id: UUID, **kwargs) -> None:
        await self.session.execute(
            update(Business).where(Business.id == business_id).values(**kwargs)
        )
