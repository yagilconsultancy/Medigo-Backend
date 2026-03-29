import uuid

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commission_config import CommissionConfig


class CommissionConfigRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active(self) -> CommissionConfig | None:
        q = select(CommissionConfig).where(CommissionConfig.is_active.is_(True))
        result = await self.session.execute(q)
        return result.scalar_one_or_none()

    async def get_latest_version(self) -> int:
        q = select(func.coalesce(func.max(CommissionConfig.version), 0))
        result = await self.session.execute(q)
        return result.scalar() or 0

    async def create_new_version(self, data: dict) -> CommissionConfig:
        # Deactivate current active
        await self.session.execute(
            update(CommissionConfig).where(CommissionConfig.is_active.is_(True)).values(is_active=False)
        )
        latest = await self.get_latest_version()
        data["version"] = latest + 1
        data["is_active"] = True
        config = CommissionConfig(**data)
        self.session.add(config)
        await self.session.flush()
        await self.session.refresh(config)
        return config
