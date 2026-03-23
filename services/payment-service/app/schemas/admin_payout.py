from uuid import UUID

from pydantic import BaseModel


class PayoutKPIsResponse(BaseModel):
    total_earnings: float
    active_drivers: int
    payouts_pending_count: int
    payouts_pending_total: float
    payouts_completed_total: float


class PayoutScheduleItem(BaseModel):
    date: str
    amount: float
    status: str
    driver_id: str


class EarningsBreakdownResponse(BaseModel):
    gross_ride_revenue: float
    platform_commission: float
    driver_payouts: float


class MonthlyEarningsPoint(BaseModel):
    month: str
    earnings: float


class DriverEarningsRow(BaseModel):
    driver_id: UUID
    driver_name: str = "Unknown"
    avatar_url: str | None = None
    fleet_name: str | None = None
    specialty: str | None = None
    city: str | None = None
    trips: int
    gross_earned: float
    commission_percent: float
    net_payout: float
    pending: float
    status: str


class PayoutConfirmationResponse(BaseModel):
    driver_id: UUID
    driver_name: str
    net_payout: float
    trips: int
    gross_earned: float
    commission: float
    commission_percent: float
    payout_schedule: str = "Weekly / Every Monday"
    payout_method: str = "Direct Deposit"
    bank_last_four: str | None = None


class SpecialtyPayoutItem(BaseModel):
    specialty: str
    display_name: str
    amount: float
    count: int
