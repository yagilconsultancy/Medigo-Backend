import calendar
import logging
from datetime import datetime, timedelta, timezone

from app.repositories.admin_revenue_repo import AdminRevenueRepository

logger = logging.getLogger(__name__)


def _get_period_ranges(period: str) -> tuple[datetime, datetime, datetime, datetime]:
    """Return (start, end, prev_start, prev_end) for the given period type."""
    now = datetime.now(timezone.utc)

    if period == "daily":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        prev_start = start - timedelta(days=1)
        prev_end = start
    elif period == "monthly":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 12:
            end = start.replace(year=now.year + 1, month=1)
        else:
            end = start.replace(month=now.month + 1)
        prev_start = (start - timedelta(days=1)).replace(day=1)
        prev_end = start
    elif period == "yearly":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(year=now.year + 1)
        prev_start = start.replace(year=now.year - 1)
        prev_end = start
    else:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        prev_start = start - timedelta(days=1)
        prev_end = start

    return start, end, prev_start, prev_end


def _get_trend_range(period: str) -> tuple[datetime, datetime]:
    """Return wider range for trend charts."""
    now = datetime.now(timezone.utc)

    if period == "daily":
        start = now - timedelta(days=7)
        end = now + timedelta(days=1)
    elif period == "monthly":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 12:
            end = start.replace(year=now.year + 1)
        else:
            end = now + timedelta(days=1)
    elif period == "yearly":
        start = now.replace(year=now.year - 4, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now + timedelta(days=1)
    else:
        start = now - timedelta(days=7)
        end = now + timedelta(days=1)

    return start, end


class AdminRevenueService:
    def __init__(self, revenue_repo: AdminRevenueRepository):
        self.revenue_repo = revenue_repo

    async def get_revenue_kpis(self, period: str) -> dict:
        start, end, prev_start, prev_end = _get_period_ranges(period)
        data = await self.revenue_repo.get_revenue_kpis(start, end, prev_start, prev_end)

        now = datetime.now(timezone.utc)
        count = data["count"]
        total = data["total_revenue"]

        if period == "daily":
            avg = total
            avg_label = f"${avg:,.2f}/day"
            peak_period = calendar.day_name[now.weekday()]
        elif period == "monthly":
            days_in_month = calendar.monthrange(now.year, now.month)[1]
            avg = round(total / max(days_in_month, 1), 2)
            avg_label = f"${avg:,.2f}/month"
            peak_period = calendar.month_name[now.month]
        elif period == "yearly":
            avg = round(total / max(now.month, 1), 2)
            avg_label = f"${avg:,.2f}/month"
            peak_period = str(now.year)
        else:
            avg = total
            avg_label = f"${avg:,.2f}"
            peak_period = "Today"

        return {
            "total_revenue": total,
            "avg_revenue": avg,
            "avg_label": avg_label,
            "peak_period": peak_period,
            "growth_rate": data["growth_rate"],
        }

    async def get_revenue_trend(self, period: str) -> list[dict]:
        start, end = _get_trend_range(period)

        if period == "daily":
            return await self.revenue_repo.get_revenue_trend_daily(start, end)
        elif period == "monthly":
            return await self.revenue_repo.get_revenue_trend_monthly(start, end)
        elif period == "yearly":
            return await self.revenue_repo.get_revenue_trend_yearly(start, end)
        else:
            return await self.revenue_repo.get_revenue_trend_daily(start, end)

    async def get_revenue_by_ride_type(self, period: str) -> list[dict]:
        start, end, _, _ = _get_period_ranges(period)
        return await self.revenue_repo.get_revenue_by_ride_type(start, end)

    async def get_revenue_by_city(self, period: str) -> list[dict]:
        start, end, _, _ = _get_period_ranges(period)
        return await self.revenue_repo.get_revenue_by_city(start, end)

    async def get_revenue_distribution(self, period: str) -> dict:
        start, end, _, _ = _get_period_ranges(period)
        return await self.revenue_repo.get_revenue_distribution(start, end)
