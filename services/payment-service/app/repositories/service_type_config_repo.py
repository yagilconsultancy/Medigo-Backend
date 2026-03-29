import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service_type_config import ServiceTypeConfig


class ServiceTypeConfigRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self, active_only: bool = False) -> list[ServiceTypeConfig]:
        q = select(ServiceTypeConfig).order_by(ServiceTypeConfig.sort_order)
        if active_only:
            q = q.where(ServiceTypeConfig.is_active.is_(True))
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def get_by_service_type(self, service_type: str) -> ServiceTypeConfig | None:
        q = select(ServiceTypeConfig).where(ServiceTypeConfig.service_type == service_type)
        result = await self.session.execute(q)
        return result.scalar_one_or_none()

    async def update_config(self, service_type: str, config: dict) -> ServiceTypeConfig | None:
        obj = await self.get_by_service_type(service_type)
        if not obj:
            return None
        obj.config = config
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def toggle_active(self, service_type: str, is_active: bool) -> ServiceTypeConfig | None:
        obj = await self.get_by_service_type(service_type)
        if not obj:
            return None
        obj.is_active = is_active
        await self.session.flush()
        await self.session.refresh(obj)
        return obj
