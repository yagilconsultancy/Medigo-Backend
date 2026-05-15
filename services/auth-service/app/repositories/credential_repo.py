from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_credential import UserCredential
from app.normalization import normalize_email, normalize_phone


class CredentialRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, credential: UserCredential) -> UserCredential:
        self.session.add(credential)
        await self.session.flush()
        return credential

    async def get_by_id(self, user_id: UUID) -> UserCredential | None:
        result = await self.session.execute(
            select(UserCredential).where(UserCredential.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> UserCredential | None:
        normalized_email = normalize_email(email)
        if not normalized_email:
            return None

        result = await self.session.execute(
            select(UserCredential).where(
                func.lower(UserCredential.email) == normalized_email
            )
        )
        return result.scalar_one_or_none()

    async def get_by_phone(self, phone: str) -> UserCredential | None:
        normalized_phone = normalize_phone(phone)
        if not normalized_phone:
            return None

        result = await self.session.execute(
            select(UserCredential).where(UserCredential.phone == normalized_phone)
        )
        return result.scalar_one_or_none()

    async def get_by_email_or_phone(
        self, email: str | None, phone: str | None
    ) -> UserCredential | None:
        if email:
            found = await self.get_by_email(email)
            if found:
                return found
        if phone:
            return await self.get_by_phone(phone)
        return None

    async def update_verified(self, user_id: UUID, is_verified: bool) -> None:
        await self.session.execute(
            update(UserCredential)
            .where(UserCredential.id == user_id)
            .values(is_verified=is_verified)
        )

    async def update_password(self, user_id: UUID, password_hash: str) -> None:
        await self.session.execute(
            update(UserCredential)
            .where(UserCredential.id == user_id)
            .values(password_hash=password_hash)
        )

    async def increment_failed_attempts(self, user_id: UUID) -> None:
        credential = await self.get_by_id(user_id)
        if credential:
            credential.failed_attempts += 1
            await self.session.flush()

    async def reset_failed_attempts(self, user_id: UUID) -> None:
        await self.session.execute(
            update(UserCredential)
            .where(UserCredential.id == user_id)
            .values(failed_attempts=0, locked_until=None)
        )

    async def lock_account(self, user_id: UUID, locked_until) -> None:
        await self.session.execute(
            update(UserCredential)
            .where(UserCredential.id == user_id)
            .values(locked_until=locked_until)
        )
