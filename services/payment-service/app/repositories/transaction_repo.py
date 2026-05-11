from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction


class TransactionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, transaction: Transaction) -> Transaction:
        self.session.add(transaction)
        await self.session.flush()
        return transaction

    async def get_by_id(self, tx_id: UUID) -> Transaction | None:
        result = await self.session.execute(
            select(Transaction).where(Transaction.id == tx_id)
        )
        return result.scalar_one_or_none()

    async def get_by_ride_id(self, ride_id: UUID) -> list[Transaction]:
        result = await self.session.execute(
            select(Transaction).where(Transaction.ride_id == ride_id)
        )
        return list(result.scalars().all())

    async def get_by_reference_id(self, reference_id: str) -> Transaction | None:
        result = await self.session.execute(
            select(Transaction).where(Transaction.reference_id == reference_id)
        )
        return result.scalar_one_or_none()

    async def get_by_order_id(self, order_id: str) -> Transaction | None:
        result = await self.session.execute(
            select(Transaction)
            .where(Transaction.description == f"Mobile PaymentIntent order_id={order_id}")
            .order_by(Transaction.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update(self, transaction: Transaction, **kwargs) -> Transaction:
        for key, value in kwargs.items():
            if hasattr(transaction, key):
                setattr(transaction, key, value)
        await self.session.flush()
        return transaction

    async def get_by_user(
        self, user_id: UUID, offset: int = 0, limit: int = 20,
        tx_type: str | None = None,
    ) -> tuple[list[Transaction], int]:
        conditions = [Transaction.user_id == user_id]
        if tx_type:
            conditions.append(Transaction.transaction_type == tx_type)

        base_query = select(Transaction).where(*conditions)

        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            base_query.offset(offset).limit(limit).order_by(Transaction.created_at.desc())
        )
        return list(result.scalars().all()), total
