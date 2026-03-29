import uuid

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.surcharge_rule import SurchargeRule


class SurchargeRuleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> list[SurchargeRule]:
        q = select(SurchargeRule).order_by(SurchargeRule.sort_order)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def get_active(self) -> list[SurchargeRule]:
        q = (
            select(SurchargeRule)
            .where(SurchargeRule.is_active.is_(True))
            .order_by(SurchargeRule.sort_order)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def get_by_id(self, rule_id: uuid.UUID) -> SurchargeRule | None:
        q = select(SurchargeRule).where(SurchargeRule.id == rule_id)
        result = await self.session.execute(q)
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> SurchargeRule:
        rule = SurchargeRule(**data)
        self.session.add(rule)
        await self.session.flush()
        await self.session.refresh(rule)
        return rule

    async def update(self, rule_id: uuid.UUID, data: dict) -> SurchargeRule | None:
        obj = await self.get_by_id(rule_id)
        if not obj:
            return None
        for k, v in data.items():
            setattr(obj, k, v)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, rule_id: uuid.UUID) -> bool:
        obj = await self.get_by_id(rule_id)
        if not obj:
            return False
        await self.session.delete(obj)
        await self.session.flush()
        return True

    async def count_active(self) -> int:
        q = select(SurchargeRule).where(SurchargeRule.is_active.is_(True))
        result = await self.session.execute(q)
        return len(result.scalars().all())

    async def count_inactive(self) -> int:
        q = select(SurchargeRule).where(SurchargeRule.is_active.is_(False))
        result = await self.session.execute(q)
        return len(result.scalars().all())
