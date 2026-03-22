import logging
from datetime import date, timedelta
from uuid import UUID

from app.models.earnings_period import EarningsPeriod
from app.repositories.earnings_period_repo import EarningsPeriodRepository
from app.repositories.earnings_repo import EarningsRepository
from app.repositories.fare_repo import FareBreakdownRepository
from app.repositories.transaction_repo import TransactionRepository
from app.models.transaction import Transaction
from mediride_common.schemas.enums import PaymentStatus, TransactionType
from mediride_common.utils import utc_now

logger = logging.getLogger(__name__)


class EarningsService:
    def __init__(
        self,
        earnings_repo: EarningsRepository,
        period_repo: EarningsPeriodRepository,
        tx_repo: TransactionRepository,
        fare_repo: FareBreakdownRepository,
    ):
        self.earnings_repo = earnings_repo
        self.period_repo = period_repo
        self.tx_repo = tx_repo
        self.fare_repo = fare_repo

    async def get_driver_balance(self, driver_id: UUID) -> dict:
        earnings = await self.earnings_repo.get_or_create(driver_id)
        return {
            "available_balance": float(earnings.available_balance),
            "total_earned": float(earnings.total_earned),
            "total_withdrawn": float(earnings.total_withdrawn),
            "pending_withdrawal": float(earnings.pending_withdrawal),
        }

    async def get_earnings_summary(self, driver_id: UUID) -> dict:
        earnings = await self.earnings_repo.get_or_create(driver_id)

        # Today's earnings
        today = utc_now().date()
        today_period = await self.period_repo.get_by_driver_period(driver_id, "daily", today)
        earnings_today = float(today_period.total_earnings) if today_period else 0
        trips_today = today_period.trip_count if today_period else 0
        hours_today = float(today_period.hours_online) if today_period else 0

        # Yesterday for change calculation
        yesterday = today - timedelta(days=1)
        yesterday_period = await self.period_repo.get_by_driver_period(driver_id, "daily", yesterday)
        earnings_yesterday = float(yesterday_period.total_earnings) if yesterday_period else 0

        change_percent = 0.0
        if earnings_yesterday > 0:
            change_percent = round(
                ((earnings_today - earnings_yesterday) / earnings_yesterday) * 100, 1
            )

        avg_per_trip = round(earnings_today / trips_today, 2) if trips_today > 0 else 0

        return {
            "available_balance": float(earnings.available_balance),
            "next_payout_date": None,
            "next_payout_method": None,
            "earnings_today": earnings_today,
            "earnings_today_change_percent": change_percent,
            "trips_today": trips_today,
            "hours_today": hours_today,
            "avg_earnings_per_trip": avg_per_trip,
        }

    async def get_earnings_breakdown(
        self, driver_id: UUID, period_type: str, start: date, end: date
    ) -> dict:
        periods = await self.period_repo.get_range(driver_id, period_type, start, end)

        totals = {
            "base_fares": 0, "distance_charges": 0, "medical_premiums": 0,
            "tips": 0, "incentives": 0, "platform_fees": 0, "net_earnings": 0,
        }
        for p in periods:
            for key in totals:
                totals[key] += float(getattr(p, key))

        totals = {k: round(v, 2) for k, v in totals.items()}
        return {
            "period_type": period_type,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            **totals,
        }

    async def get_performance_data(self, driver_id: UUID, period_type: str) -> list[dict]:
        today = utc_now().date()

        if period_type == "daily":
            start = today
            end = today
            periods = await self.period_repo.get_range(driver_id, "hourly", start, end)
            # Return hourly labels
            return [
                {"label": f"{i}AM" if i < 12 else f"{i-12 or 12}PM",
                 "earnings": 0, "trip_count": 0}
                for i in range(8, 24, 2)
            ]
        elif period_type == "weekly":
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
            periods = await self.period_repo.get_range(driver_id, "daily", start, end)
            days = ["M", "T", "W", "T", "F", "S", "S"]
            data = []
            for i, day in enumerate(days):
                d = start + timedelta(days=i)
                period = next((p for p in periods if p.period_start == d), None)
                data.append({
                    "label": day,
                    "earnings": float(period.total_earnings) if period else 0,
                    "trip_count": period.trip_count if period else 0,
                })
            return data
        else:  # monthly
            data = []
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            for i, month in enumerate(months, 1):
                month_start = date(today.year, i, 1)
                if i == 12:
                    month_end = date(today.year + 1, 1, 1) - timedelta(days=1)
                else:
                    month_end = date(today.year, i + 1, 1) - timedelta(days=1)
                periods = await self.period_repo.get_range(
                    driver_id, "monthly", month_start, month_end
                )
                total = sum(float(p.total_earnings) for p in periods) if periods else 0
                trips = sum(p.trip_count for p in periods) if periods else 0
                data.append({"label": month, "earnings": total, "trip_count": trips})
            return data

    async def get_recent_history(self, driver_id: UUID, days: int = 7) -> list[dict]:
        periods = await self.period_repo.get_recent_daily(driver_id, days)
        today = utc_now().date()

        history = []
        for period in periods:
            if period.period_start == today:
                label = "Today"
            elif period.period_start == today - timedelta(days=1):
                label = "Yesterday"
            else:
                label = period.period_start.strftime("%b %d")

            history.append({
                "date": period.period_start.isoformat(),
                "label": label,
                "trip_count": period.trip_count,
                "earnings": float(period.total_earnings),
                "change_percent": 0,
            })
        return history

    async def record_ride_earnings(
        self, ride_id: UUID, driver_id: UUID, fare_amount: float
    ) -> None:
        # Add to driver balance
        await self.earnings_repo.add_earnings(driver_id, fare_amount)

        # Record transaction
        tx = Transaction(
            ride_id=ride_id,
            user_id=driver_id,
            transaction_type=TransactionType.RIDE_PAYMENT,
            amount=fare_amount,
            status=PaymentStatus.COMPLETED,
            description=f"Earnings from ride {ride_id}",
        )
        await self.tx_repo.create(tx)

        logger.info(f"Recorded ${fare_amount} earnings for driver {driver_id} from ride {ride_id}")
