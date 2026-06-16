from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def list_by_role(
        self, role: str, offset: int = 0, limit: int = 20, business_id: UUID | None = None
    ) -> tuple[list[User], int]:
        query = select(User).where(User.role == role, User.deleted_at.is_(None))
        if business_id:
            query = query.where(User.business_id == business_id)

        # Count
        from sqlalchemy import func
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        # Paginated results
        result = await self.session.execute(
            query.offset(offset).limit(limit).order_by(User.created_at.desc())
        )
        return list(result.scalars().all()), total

    async def update(self, user_id: UUID, **kwargs) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(**kwargs)
        )
        await self.session.flush()
        self.session.expire_all()

    async def soft_delete(self, user_id: UUID) -> None:
        await self.session.execute(
            update(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .values(deleted_at=datetime.now(timezone.utc), is_active=False)
        )
        await self.session.flush()
