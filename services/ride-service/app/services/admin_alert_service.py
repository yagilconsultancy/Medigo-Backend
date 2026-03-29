from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.safety_alert import SafetyAlert
from app.repositories.safety_alert_repo import SafetyAlertRepository


class AdminAlertService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SafetyAlertRepository(session)

    async def get_kpis(self) -> dict:
        active = await self.repo.count_active()
        route_dev = await self.repo.count_by_category("route_deviation")
        late = await self.repo.count_by_category("late_arrival")
        resolved = await self.repo.count_resolved_today()
        return {
            "active": active,
            "route_deviations": route_dev,
            "late_arrivals": late,
            "resolved_today": resolved,
        }

    async def get_feed(
        self,
        page: int = 1,
        page_size: int = 20,
        category: str | None = None,
        severity: str | None = None,
        status: str | None = None,
    ) -> dict:
        offset = (page - 1) * page_size
        items, total = await self.repo.get_paginated(
            offset=offset, limit=page_size,
            category=category, severity=severity, status=status,
        )
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def get_detail(self, alert_id: UUID) -> SafetyAlert | None:
        return await self.repo.get_by_id(alert_id)

    async def acknowledge(self, alert_id: UUID, admin_id: UUID) -> SafetyAlert | None:
        alert = await self.repo.get_by_id(alert_id)
        if not alert:
            return None
        return await self.repo.acknowledge(alert, admin_id)

    async def resolve(self, alert_id: UUID) -> SafetyAlert | None:
        alert = await self.repo.get_by_id(alert_id)
        if not alert:
            return None
        return await self.repo.resolve(alert)
