from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.withdrawal import Withdrawal


class WithdrawalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, withdrawal: Withdrawal) -> Withdrawal:
        self.session.add(withdrawal)
        await self.session.flush()
        return withdrawal

    async def get_by_id(self, w_id: UUID) -> Withdrawal | None:
        result = await self.session.execute(
            select(Withdrawal).where(Withdrawal.id == w_id)
        )
        return result.scalar_one_or_none()

    async def get_by_driver(
        self, driver_id: UUID, offset: int = 0, limit: int = 20
    ) -> tuple[list[Withdrawal], int]:
        base_query = select(Withdrawal).where(Withdrawal.driver_id == driver_id)

        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            base_query.offset(offset).limit(limit).order_by(Withdrawal.created_at.desc())
        )
        return list(result.scalars().all()), total

    async def update(self, w_id: UUID, **kwargs) -> None:
        await self.session.execute(
            update(Withdrawal).where(Withdrawal.id == w_id).values(**kwargs)
        )
