from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_session import UserSession
from mediride_common.utils import utc_now


class SessionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_session: UserSession) -> UserSession:
        self.session.add(user_session)
        await self.session.flush()
        await self.session.refresh(user_session)
        return user_session

    async def get_by_id(self, session_id: UUID) -> UserSession | None:
        result = await self.session.execute(
            select(UserSession).where(UserSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_user(self, user_id: UUID) -> list[UserSession]:
        result = await self.session.execute(
            select(UserSession)
            .where(UserSession.user_id == user_id, UserSession.is_active == True)
            .order_by(UserSession.last_active_at.desc())
        )
        return list(result.scalars().all())

    async def deactivate(self, session_id: UUID) -> None:
        await self.session.execute(
            update(UserSession)
            .where(UserSession.id == session_id)
            .values(is_active=False)
        )

    async def deactivate_all(self, user_id: UUID, except_id: UUID | None = None) -> None:
        query = (
            update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.is_active == True)
        )
        if except_id:
            query = query.where(UserSession.id != except_id)
        await self.session.execute(query.values(is_active=False))

    async def update_last_active(self, session_id: UUID) -> None:
        await self.session.execute(
            update(UserSession)
            .where(UserSession.id == session_id)
            .values(last_active_at=utc_now())
        )
