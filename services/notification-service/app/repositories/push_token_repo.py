from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.push_token import PushToken
from mediride_common.utils import utc_now


class PushTokenRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(self, user_id: UUID, token: str, platform: str) -> PushToken:
        """Create or update a push token for a user."""
        result = await self.session.execute(
            select(PushToken).where(PushToken.user_id == user_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.token = token
            existing.platform = platform
            existing.updated_at = utc_now()
            await self.session.flush()
            await self.session.refresh(existing)
            return existing

        push_token = PushToken(
            user_id=user_id,
            token=token,
            platform=platform,
        )
        self.session.add(push_token)
        await self.session.flush()
        await self.session.refresh(push_token)
        return push_token

    async def get_by_user_id(self, user_id: UUID) -> PushToken | None:
        result = await self.session.execute(
            select(PushToken).where(PushToken.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def delete_by_user_id(self, user_id: UUID) -> bool:
        result = await self.session.execute(
            delete(PushToken).where(PushToken.user_id == user_id)
        )
        return result.rowcount > 0
