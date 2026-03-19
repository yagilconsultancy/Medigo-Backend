from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dialysis_rate_plan import DialysisRatePlan


class DialysisRatePlanRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_matching_plan(
        self, origin: str, destination: str
    ) -> DialysisRatePlan | None:
        result = await self.session.execute(
            select(DialysisRatePlan).where(
                DialysisRatePlan.is_active.is_(True),
                DialysisRatePlan.origin_area.ilike(f"%{origin}%"),
                DialysisRatePlan.destination_area.ilike(f"%{destination}%"),
            )
        )
        return result.scalar_one_or_none()

    async def get_all(self, active_only: bool = False) -> list[DialysisRatePlan]:
        stmt = select(DialysisRatePlan).order_by(DialysisRatePlan.plan_name)
        if active_only:
            stmt = stmt.where(DialysisRatePlan.is_active.is_(True))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, plan_id: UUID) -> DialysisRatePlan | None:
        result = await self.session.execute(
            select(DialysisRatePlan).where(DialysisRatePlan.id == plan_id)
        )
        return result.scalar_one_or_none()

    async def create(self, plan: DialysisRatePlan) -> DialysisRatePlan:
        self.session.add(plan)
        await self.session.flush()
        return plan

    async def update(self, plan_id: UUID, **kwargs) -> DialysisRatePlan | None:
        plan = await self.get_by_id(plan_id)
        if not plan:
            return None
        for key, value in kwargs.items():
            setattr(plan, key, value)
        await self.session.flush()
        return plan

    async def deactivate(self, plan_id: UUID) -> DialysisRatePlan | None:
        return await self.update(plan_id, is_active=False)
