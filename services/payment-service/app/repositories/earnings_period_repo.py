from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.earnings_period import EarningsPeriod


class EarningsPeriodRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(self, period: EarningsPeriod) -> EarningsPeriod:
        existing = await self.get_by_driver_period(
            period.driver_id, period.period_type, period.period_start
        )
        if existing:
            for field in [
                "total_earnings", "trip_count", "hours_online", "base_fares",
                "distance_charges", "medical_premiums", "tips", "incentives",
                "platform_fees", "net_earnings",
            ]:
                setattr(existing, field, getattr(period, field))
            await self.session.flush()
            return existing
        self.session.add(period)
        await self.session.flush()
        return period

    async def get_by_driver_period(
        self, driver_id: UUID, period_type: str, period_start: date
    ) -> EarningsPeriod | None:
        result = await self.session.execute(
            select(EarningsPeriod).where(
                EarningsPeriod.driver_id == driver_id,
                EarningsPeriod.period_type == period_type,
                EarningsPeriod.period_start == period_start,
            )
        )
        return result.scalar_one_or_none()

    async def get_range(
        self, driver_id: UUID, period_type: str, start: date, end: date
    ) -> list[EarningsPeriod]:
        result = await self.session.execute(
            select(EarningsPeriod).where(
                EarningsPeriod.driver_id == driver_id,
                EarningsPeriod.period_type == period_type,
                EarningsPeriod.period_start >= start,
                EarningsPeriod.period_end <= end,
            ).order_by(EarningsPeriod.period_start.asc())
        )
        return list(result.scalars().all())

    async def get_recent_daily(
        self, driver_id: UUID, days: int = 7
    ) -> list[EarningsPeriod]:
        from datetime import timedelta
        from mediride_common.utils import utc_now

        end = utc_now().date()
        start = end - timedelta(days=days)
        return await self.get_range(driver_id, "daily", start, end)
