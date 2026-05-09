from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.safety_alert import SafetyAlert


class SafetyAlertRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def next_number(self) -> int:
        result = await self.session.execute(text("SELECT nextval('alert_seq')"))
        return result.scalar_one()

    async def create(self, alert: SafetyAlert) -> SafetyAlert:
        self.session.add(alert)
        await self.session.flush()
        return alert

    async def get_by_id(self, alert_id: UUID) -> SafetyAlert | None:
        result = await self.session.execute(
            select(SafetyAlert).where(SafetyAlert.id == alert_id)
        )
        return result.scalar_one_or_none()

    async def get_paginated(
        self,
        offset: int = 0,
        limit: int = 20,
        category: str | None = None,
        severity: str | None = None,
        status: str | None = None,
    ) -> tuple[list[SafetyAlert], int]:
        query = select(SafetyAlert)
        count_query = select(func.count(SafetyAlert.id))

        if category:
            query = query.where(SafetyAlert.category == category)
            count_query = count_query.where(SafetyAlert.category == category)
        if severity:
            query = query.where(SafetyAlert.severity == severity)
            count_query = count_query.where(SafetyAlert.severity == severity)
        if status:
            query = query.where(SafetyAlert.status == status)
            count_query = count_query.where(SafetyAlert.status == status)

        total = (await self.session.execute(count_query)).scalar_one()
        rows = (
            await self.session.execute(
                query.order_by(SafetyAlert.created_at.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), total

    async def count_active(self) -> int:
        result = await self.session.execute(
            select(func.count(SafetyAlert.id)).where(SafetyAlert.status == "active")
        )
        return result.scalar_one()

    async def count_by_category(self, category: str) -> int:
        result = await self.session.execute(
            select(func.count(SafetyAlert.id)).where(SafetyAlert.category == category)
        )
        return result.scalar_one()

    async def count_resolved_today(self) -> int:
        from app.config import settings
        from mediride_common.utils import start_of_local_day_utc

        today_start = start_of_local_day_utc(tz_name=settings.DEFAULT_TIMEZONE)
        result = await self.session.execute(
            select(func.count(SafetyAlert.id)).where(
                SafetyAlert.status == "resolved",
                SafetyAlert.resolved_at >= today_start,
            )
        )
        return result.scalar_one()

    async def acknowledge(self, alert: SafetyAlert, admin_id: UUID) -> SafetyAlert:
        from datetime import datetime, timezone
        alert.status = "acknowledged"
        alert.acknowledged_at = datetime.now(timezone.utc)
        alert.acknowledged_by = admin_id
        await self.session.flush()
        await self.session.refresh(alert)
        return alert

    async def resolve(self, alert: SafetyAlert) -> SafetyAlert:
        from datetime import datetime, timezone
        alert.status = "resolved"
        alert.resolved_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(alert)
        return alert
