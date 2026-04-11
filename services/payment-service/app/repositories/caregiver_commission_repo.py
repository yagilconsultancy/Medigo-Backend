from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.caregiver_commission_config import CaregiverCommissionConfig


class CaregiverCommissionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_specialty(self, specialty: str) -> CaregiverCommissionConfig | None:
        """Get active commission config for a specific specialty."""
        query = select(CaregiverCommissionConfig).where(
            CaregiverCommissionConfig.specialty == specialty,
            CaregiverCommissionConfig.is_active == True
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all_active(self) -> list[CaregiverCommissionConfig]:
        """Get all active commission configs."""
        query = select(CaregiverCommissionConfig).where(
            CaregiverCommissionConfig.is_active == True
        ).order_by(CaregiverCommissionConfig.specialty)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, config_id: UUID) -> CaregiverCommissionConfig | None:
        """Get commission config by ID."""
        query = select(CaregiverCommissionConfig).where(
            CaregiverCommissionConfig.id == config_id
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create(self, config: CaregiverCommissionConfig) -> CaregiverCommissionConfig:
        """Create a new commission config."""
        self.session.add(config)
        await self.session.flush()
        await self.session.refresh(config)
        return config

    async def update(
        self, config_id: UUID, **kwargs
    ) -> CaregiverCommissionConfig | None:
        """Update commission config."""
        config = await self.get_by_id(config_id)
        if not config:
            return None

        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)

        await self.session.flush()
        await self.session.refresh(config)
        return config

    async def delete(self, config_id: UUID) -> bool:
        """Delete commission config."""
        config = await self.get_by_id(config_id)
        if not config:
            return False

        await self.session.delete(config)
        await self.session.flush()
        return True
