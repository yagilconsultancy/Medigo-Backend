from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_settings import UserSettings


class SettingsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_user_id(self, user_id: UUID) -> UserSettings | None:
        result = await self.session.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(self, settings: UserSettings) -> UserSettings:
        self.session.add(settings)
        await self.session.flush()
        await self.session.refresh(settings)
        return settings

    async def update(self, user_id: UUID, **kwargs) -> None:
        await self.session.execute(
            update(UserSettings).where(UserSettings.user_id == user_id).values(**kwargs)
        )

    async def get_or_create(self, user_id: UUID) -> UserSettings:
        settings = await self.get_by_user_id(user_id)
        if not settings:
            settings = UserSettings(user_id=user_id)
            settings = await self.create(settings)
        return settings
