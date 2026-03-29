import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cancellation_policy import CancellationPolicy


class CancellationPolicyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self, active_only: bool = True) -> list[CancellationPolicy]:
        q = select(CancellationPolicy).order_by(CancellationPolicy.sort_order)
        if active_only:
            q = q.where(CancellationPolicy.is_active.is_(True))
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def get_by_service_type(self, service_type: str) -> list[CancellationPolicy]:
        q = (
            select(CancellationPolicy)
            .where(CancellationPolicy.service_type == service_type, CancellationPolicy.is_active.is_(True))
            .order_by(CancellationPolicy.sort_order)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def get_by_id(self, policy_id: uuid.UUID) -> CancellationPolicy | None:
        q = select(CancellationPolicy).where(CancellationPolicy.id == policy_id)
        result = await self.session.execute(q)
        return result.scalar_one_or_none()

    async def update_policy(self, policy_id: uuid.UUID, data: dict) -> CancellationPolicy | None:
        obj = await self.get_by_id(policy_id)
        if not obj:
            return None
        for k, v in data.items():
            setattr(obj, k, v)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def bulk_update(self, updates: list[dict]) -> int:
        count = 0
        for item in updates:
            policy_id = item.pop("id")
            obj = await self.get_by_id(uuid.UUID(str(policy_id)))
            if obj:
                for k, v in item.items():
                    setattr(obj, k, v)
                count += 1
        await self.session.flush()
        return count

    async def count_service_types(self) -> int:
        from sqlalchemy import func
        q = select(func.count(func.distinct(CancellationPolicy.service_type))).where(
            CancellationPolicy.is_active.is_(True)
        )
        result = await self.session.execute(q)
        return result.scalar() or 0

    async def count_fee_tiers(self) -> int:
        from sqlalchemy import func
        q = select(func.count(func.distinct(CancellationPolicy.cancellation_window))).where(
            CancellationPolicy.is_active.is_(True)
        )
        result = await self.session.execute(q)
        return result.scalar() or 0

    async def max_fee(self) -> float:
        from sqlalchemy import func
        q = select(func.coalesce(func.max(CancellationPolicy.fee), 0)).where(
            CancellationPolicy.is_active.is_(True)
        )
        result = await self.session.execute(q)
        return float(result.scalar() or 0)
