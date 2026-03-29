from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_settings import SecuritySettings


class SecuritySettingsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active(self) -> SecuritySettings | None:
        result = await self.session.execute(
            select(SecuritySettings).where(SecuritySettings.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def update_settings(self, admin_id: UUID, **updates) -> SecuritySettings:
        updates["updated_by"] = admin_id
        await self.session.execute(
            update(SecuritySettings)
            .where(SecuritySettings.is_active.is_(True))
            .values(**updates)
        )
        settings = await self.get_active()
        if settings:
            await self.session.refresh(settings)
        return settings
