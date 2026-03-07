from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.password_reset import PasswordResetToken
from mediride_common.utils import utc_now


class PasswordResetRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, token: PasswordResetToken) -> PasswordResetToken:
        self.session.add(token)
        await self.session.flush()
        return token

    async def get_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        result = await self.session.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def mark_used(self, token_id: UUID) -> None:
        await self.session.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.id == token_id)
            .values(used_at=utc_now())
        )

    async def invalidate_all_for_user(self, user_id: UUID) -> None:
        await self.session.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=utc_now())
        )
