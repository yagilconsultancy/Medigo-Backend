from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment_method import PaymentMethod
from mediride_common.utils import utc_now


class PaymentMethodRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, method: PaymentMethod) -> PaymentMethod:
        self.session.add(method)
        await self.session.flush()
        return method

    async def get_by_id(self, pm_id: UUID) -> PaymentMethod | None:
        result = await self.session.execute(
            select(PaymentMethod).where(
                PaymentMethod.id == pm_id,
                PaymentMethod.deleted_at.is_(None),
                PaymentMethod.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: UUID) -> list[PaymentMethod]:
        result = await self.session.execute(
            select(PaymentMethod).where(
                PaymentMethod.user_id == user_id,
                PaymentMethod.deleted_at.is_(None),
                PaymentMethod.is_active.is_(True),
            ).order_by(PaymentMethod.is_default.desc(), PaymentMethod.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_default(self, user_id: UUID) -> PaymentMethod | None:
        result = await self.session.execute(
            select(PaymentMethod).where(
                PaymentMethod.user_id == user_id,
                PaymentMethod.is_default.is_(True),
                PaymentMethod.deleted_at.is_(None),
                PaymentMethod.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def set_default(self, user_id: UUID, pm_id: UUID) -> None:
        # Unset all defaults for user
        await self.session.execute(
            update(PaymentMethod)
            .where(PaymentMethod.user_id == user_id)
            .values(is_default=False)
        )
        # Set new default
        await self.session.execute(
            update(PaymentMethod)
            .where(PaymentMethod.id == pm_id)
            .values(is_default=True)
        )

    async def soft_delete(self, pm_id: UUID) -> None:
        await self.session.execute(
            update(PaymentMethod)
            .where(PaymentMethod.id == pm_id)
            .values(deleted_at=utc_now(), is_active=False)
        )
