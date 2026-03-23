from datetime import datetime

from sqlalchemy import Date, Integer,cast, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fare_breakdown import FareBreakdown
from app.models.transaction import Transaction


class AdminRevenueRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_revenue_kpis(
        self,
        start: datetime,
        end: datetime,
        prev_start: datetime,
        prev_end: datetime,
    ) -> dict:
        # Current period
        curr = await self.session.execute(
            select(
                func.coalesce(func.sum(FareBreakdown.total_fare), 0).label("total"),
                func.count().label("count"),
            ).where(
                FareBreakdown.created_at >= start,
                FareBreakdown.created_at < end,
            )
        )
        curr_row = curr.one()

        # Previous period
        prev = await self.session.execute(
            select(
                func.coalesce(func.sum(FareBreakdown.total_fare), 0).label("total"),
            ).where(
                FareBreakdown.created_at >= prev_start,
                FareBreakdown.created_at < prev_end,
            )
        )
        prev_row = prev.one()

        curr_total = float(curr_row.total)
        prev_total = float(prev_row.total)
        growth_rate = 0.0
        if prev_total > 0:
            growth_rate = round(((curr_total - prev_total) / prev_total) * 100, 1)

        return {
            "total_revenue": curr_total,
            "count": curr_row.count,
            "prev_total": prev_total,
            "growth_rate": growth_rate,
        }

    async def get_revenue_trend_daily(
        self, start: datetime, end: datetime
    ) -> list[dict]:
        result = await self.session.execute(
            select(
                cast(FareBreakdown.created_at, Date).label("date"),
                func.sum(FareBreakdown.total_fare).label("revenue"),
                func.count().label("count"),
            )
            .where(
                FareBreakdown.created_at >= start,
                FareBreakdown.created_at < end,
            )
            .group_by(cast(FareBreakdown.created_at, Date))
            .order_by(cast(FareBreakdown.created_at, Date))
        )
        return [
            {"label": str(r.date), "revenue": float(r.revenue), "count": r.count}
            for r in result.all()
        ]

    async def get_revenue_trend_monthly(
        self, start: datetime, end: datetime
    ) -> list[dict]:
        result = await self.session.execute(
            select(
                extract("year", FareBreakdown.created_at).label("year"),
                extract("month", FareBreakdown.created_at).label("month"),
                func.sum(FareBreakdown.total_fare).label("revenue"),
                func.count().label("count"),
            )
            .where(
                FareBreakdown.created_at >= start,
                FareBreakdown.created_at < end,
            )
            .group_by(
                extract("year", FareBreakdown.created_at),
                extract("month", FareBreakdown.created_at),
            )
            .order_by(
                extract("year", FareBreakdown.created_at),
                extract("month", FareBreakdown.created_at),
            )
        )
        months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        return [
            {
                "label": f"{months[int(r.month)]} {int(r.year)}",
                "revenue": float(r.revenue),
                "count": r.count,
            }
            for r in result.all()
        ]

    async def get_revenue_trend_yearly(
        self, start: datetime, end: datetime
    ) -> list[dict]:
        result = await self.session.execute(
            select(
                extract("year", FareBreakdown.created_at).cast(Integer).label("year"),
                func.sum(FareBreakdown.total_fare).label("revenue"),
                func.count().label("count"),
            )
            .where(
                FareBreakdown.created_at >= start,
                FareBreakdown.created_at < end,
            )
            .group_by(extract("year", FareBreakdown.created_at))
            .order_by(extract("year", FareBreakdown.created_at))
        )
        return [
            {"label": str(r.year), "revenue": float(r.revenue), "count": r.count}
            for r in result.all()
        ]

    async def get_revenue_by_ride_type(
        self, start: datetime, end: datetime
    ) -> list[dict]:
        result = await self.session.execute(
            select(
                FareBreakdown.ride_type,
                func.sum(FareBreakdown.total_fare).label("revenue"),
            )
            .where(
                FareBreakdown.created_at >= start,
                FareBreakdown.created_at < end,
                FareBreakdown.ride_type.isnot(None),
            )
            .group_by(FareBreakdown.ride_type)
            .order_by(func.sum(FareBreakdown.total_fare).desc())
        )

        display_names = {
            "ambulatory": "Standard Medical",
            "standard": "Standard Medical",
            "wheelchair": "Wheelchair Accessible",
            "stretcher": "Stretcher Transport",
        }

        return [
            {
                "ride_type": r.ride_type,
                "display_name": display_names.get(r.ride_type, r.ride_type.replace("_", " ").title()),
                "revenue": float(r.revenue),
            }
            for r in result.all()
        ]

    async def get_revenue_by_city(
        self, start: datetime, end: datetime
    ) -> list[dict]:
        result = await self.session.execute(
            select(
                FareBreakdown.pickup_city,
                func.sum(FareBreakdown.total_fare).label("revenue"),
            )
            .where(
                FareBreakdown.created_at >= start,
                FareBreakdown.created_at < end,
                FareBreakdown.pickup_city.isnot(None),
            )
            .group_by(FareBreakdown.pickup_city)
            .order_by(func.sum(FareBreakdown.total_fare).desc())
            .limit(10)
        )
        rows = result.all()
        return [
            {"city": r.pickup_city, "revenue": float(r.revenue), "rank": i + 1}
            for i, r in enumerate(rows)
        ]

    async def get_revenue_distribution(
        self, start: datetime, end: datetime
    ) -> dict:
        fare_result = await self.session.execute(
            select(
                func.coalesce(func.sum(FareBreakdown.total_fare), 0).label("gross"),
                func.coalesce(func.sum(FareBreakdown.platform_fee), 0).label("commission"),
                func.coalesce(func.sum(FareBreakdown.driver_earnings), 0).label("driver_payouts"),
            ).where(
                FareBreakdown.created_at >= start,
                FareBreakdown.created_at < end,
            )
        )
        fare_row = fare_result.one()

        # Fleet payouts = driver_earnings where business_id is set
        fleet_result = await self.session.execute(
            select(
                func.coalesce(func.sum(FareBreakdown.driver_earnings), 0).label("fleet_payouts"),
            ).where(
                FareBreakdown.created_at >= start,
                FareBreakdown.created_at < end,
                FareBreakdown.business_id.isnot(None),
            )
        )
        fleet_row = fleet_result.one()

        # Refunds
        refund_result = await self.session.execute(
            select(
                func.coalesce(func.sum(Transaction.amount), 0).label("refunds"),
            ).where(
                Transaction.transaction_type == "refund",
                Transaction.status == "completed",
                Transaction.created_at >= start,
                Transaction.created_at < end,
            )
        )
        refund_row = refund_result.one()

        return {
            "gross_revenue": float(fare_row.gross),
            "platform_commission": float(fare_row.commission),
            "driver_payouts": float(fare_row.driver_payouts),
            "fleet_payouts": float(fleet_row.fleet_payouts),
            "refunds_issued": float(refund_row.refunds),
        }
