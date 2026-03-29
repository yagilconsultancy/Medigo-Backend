import uuid

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pricing_change_log import PricingChangeLog


class PricingChangeLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict) -> PricingChangeLog:
        # Get next log number from sequence
        result = await self.session.execute(text("SELECT nextval('pricing_log_seq')"))
        log_number = result.scalar()
        data["log_number"] = log_number
        log = PricingChangeLog(**data)
        self.session.add(log)
        await self.session.flush()
        await self.session.refresh(log)
        return log

    async def get_recent(self, limit: int = 10) -> list[PricingChangeLog]:
        q = (
            select(PricingChangeLog)
            .order_by(PricingChangeLog.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def get_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        category: str | None = None,
        search: str | None = None,
    ) -> tuple[list[PricingChangeLog], int]:
        q = select(PricingChangeLog)
        count_q = select(func.count()).select_from(PricingChangeLog)

        if category:
            q = q.where(PricingChangeLog.category == category)
            count_q = count_q.where(PricingChangeLog.category == category)

        if search:
            pattern = f"%{search}%"
            q = q.where(
                PricingChangeLog.change_description.ilike(pattern)
                | PricingChangeLog.admin_name.ilike(pattern)
            )
            count_q = count_q.where(
                PricingChangeLog.change_description.ilike(pattern)
                | PricingChangeLog.admin_name.ilike(pattern)
            )

        total_result = await self.session.execute(count_q)
        total = total_result.scalar() or 0

        q = q.order_by(PricingChangeLog.created_at.desc())
        q = q.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(q)
        items = list(result.scalars().all())

        return items, total

    async def get_all_for_export(self, category: str | None = None) -> list[PricingChangeLog]:
        q = select(PricingChangeLog).order_by(PricingChangeLog.created_at.desc())
        if category:
            q = q.where(PricingChangeLog.category == category)
        result = await self.session.execute(q)
        return list(result.scalars().all())
