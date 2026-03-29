from uuid import UUID

from pydantic import BaseModel


class FleetEarningsKPIs(BaseModel):
    total_revenue: float
    total_payouts: float
    revenue_change_percent: float
    payout_change_percent: float
    revenue_trend: str  # "up", "down", "flat"
    payout_trend: str


class FleetRevenueTrendPoint(BaseModel):
    date: str
    revenue: float


class FleetRevenueTrendResponse(BaseModel):
    period_days: int
    trend: list[FleetRevenueTrendPoint]


class FleetEarningsBreakdownRow(BaseModel):
    fleet_id: UUID
    fleet_name: str
    trips: int
    revenue: float
    commission: float
    net_earnings: float
    avg_per_trip: float
