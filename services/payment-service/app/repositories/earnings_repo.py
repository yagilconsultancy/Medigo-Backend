from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.driver_earnings import DriverEarnings


class EarningsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, driver_id: UUID) -> DriverEarnings:
        result = await self.session.execute(
            select(DriverEarnings).where(DriverEarnings.driver_id == driver_id)
        )
        earnings = result.scalar_one_or_none()
        if not earnings:
            earnings = DriverEarnings(driver_id=driver_id)
            self.session.add(earnings)
            await self.session.flush()
        return earnings

    async def get_balance(self, driver_id: UUID) -> DriverEarnings | None:
        result = await self.session.execute(
            select(DriverEarnings).where(DriverEarnings.driver_id == driver_id)
        )
        return result.scalar_one_or_none()

    async def add_earnings(self, driver_id: UUID, amount: float) -> DriverEarnings:
        earnings = await self.get_or_create(driver_id)
        new_balance = float(earnings.available_balance) + amount
        new_total = float(earnings.total_earned) + amount
        await self.session.execute(
            update(DriverEarnings)
            .where(DriverEarnings.driver_id == driver_id)
            .values(available_balance=new_balance, total_earned=new_total)
        )
        await self.session.flush()
        result = await self.session.execute(
            select(DriverEarnings).where(DriverEarnings.driver_id == driver_id)
        )
        return result.scalar_one()

    async def deduct_for_withdrawal(self, driver_id: UUID, amount: float) -> DriverEarnings:
        earnings = await self.get_or_create(driver_id)
        new_balance = float(earnings.available_balance) - amount
        new_pending = float(earnings.pending_withdrawal) + amount
        await self.session.execute(
            update(DriverEarnings)
            .where(DriverEarnings.driver_id == driver_id)
            .values(available_balance=new_balance, pending_withdrawal=new_pending)
        )
        await self.session.flush()
        result = await self.session.execute(
            select(DriverEarnings).where(DriverEarnings.driver_id == driver_id)
        )
        return result.scalar_one()

    async def complete_withdrawal(self, driver_id: UUID, amount: float) -> None:
        await self.session.execute(
            update(DriverEarnings)
            .where(DriverEarnings.driver_id == driver_id)
            .values(
                pending_withdrawal=DriverEarnings.pending_withdrawal - amount,
                total_withdrawn=DriverEarnings.total_withdrawn + amount,
            )
        )

    async def reverse_withdrawal_deduction(self, driver_id: UUID, amount: float) -> None:
        """Reverse a failed withdrawal: move funds from pending back to available."""
        await self.session.execute(
            update(DriverEarnings)
            .where(DriverEarnings.driver_id == driver_id)
            .values(
                available_balance=DriverEarnings.available_balance + amount,
                pending_withdrawal=DriverEarnings.pending_withdrawal - amount,
            )
        )
