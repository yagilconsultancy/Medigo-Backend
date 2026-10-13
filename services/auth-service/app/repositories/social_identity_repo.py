from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.social_identity import SocialIdentity


class SocialIdentityRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, provider: str, subject: str) -> SocialIdentity | None:
        result = await self.session.execute(
            select(SocialIdentity).where(
                SocialIdentity.provider == provider,
                SocialIdentity.subject == subject,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self, user_id: UUID, provider: str, subject: str, email: str | None
    ) -> SocialIdentity:
        identity = SocialIdentity(
            user_id=user_id, provider=provider, subject=subject, email=email
        )
        self.session.add(identity)
        await self.session.flush()
        return identity
