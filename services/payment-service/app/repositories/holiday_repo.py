from datetime import date
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holiday import Holiday


class HolidayRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def is_holiday(self, check_date: date) -> bool:
        result = await self.session.execute(
            select(Holiday).where(
                Holiday.date == check_date,
                Holiday.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_all(self, year: int | None = None) -> list[Holiday]:
        stmt = select(Holiday).order_by(Holiday.date)
        if year is not None:
            from sqlalchemy import extract
            stmt = stmt.where(extract("year", Holiday.date) == year)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, holiday: Holiday) -> Holiday:
        self.session.add(holiday)
        await self.session.flush()
        return holiday

    async def delete_by_id(self, holiday_id: UUID) -> bool:
        result = await self.session.execute(
            delete(Holiday).where(Holiday.id == holiday_id)
        )
        return result.rowcount > 0
