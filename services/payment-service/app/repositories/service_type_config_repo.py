import uuid
from uuid import UUID

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

    async def get_by_id(self, config_id: UUID) -> ServiceTypeConfig | None:
        """Get service type config by ID."""
        q = select(ServiceTypeConfig).where(ServiceTypeConfig.id == config_id)
        result = await self.session.execute(q)
        return result.scalar_one_or_none()

    async def get_by_service_type(self, service_type: str) -> ServiceTypeConfig | None:
        q = select(ServiceTypeConfig).where(ServiceTypeConfig.service_type == service_type)
        result = await self.session.execute(q)
        return result.scalar_one_or_none()

    async def create(self, config: ServiceTypeConfig) -> ServiceTypeConfig:
        """Create a new service type config."""
        self.session.add(config)
        await self.session.flush()
        await self.session.refresh(config)
        return config

    async def update(self, config_id: UUID, **kwargs) -> ServiceTypeConfig | None:
        """Update service type config by ID."""
        obj = await self.get_by_id(config_id)
        if not obj:
            return None
        for key, value in kwargs.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

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

    async def delete(self, config_id: UUID) -> bool:
        """Delete a service type config."""
        obj = await self.get_by_id(config_id)
        if not obj:
            return False
        await self.session.delete(obj)
        await self.session.flush()
        return True
