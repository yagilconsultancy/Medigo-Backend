from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EarningsBalanceResponse(BaseModel):
    available_balance: float
    total_earned: float
    total_withdrawn: float
    pending_withdrawal: float


class EarningsSummaryResponse(BaseModel):
    available_balance: float
    next_payout_date: str | None = None
    next_payout_method: str | None = None
    earnings_today: float
    earnings_today_change_percent: float
    trips_today: int
    hours_today: float
    avg_earnings_per_trip: float


class EarningsBreakdownResponse(BaseModel):
    period_type: str
    period_start: str
    period_end: str
    base_fares: float
    distance_charges: float
    medical_premiums: float
    tips: float
    incentives: float
    platform_fees: float
    net_earnings: float


class EarningsBreakdownRequest(BaseModel):
    period_type: str = "weekly"
    start_date: date
    end_date: date


class PerformanceDataPoint(BaseModel):
    label: str
    earnings: float
    trip_count: int


class EarningsHistoryItem(BaseModel):
    date: str
    label: str
    trip_count: int
    earnings: float
    change_percent: float
