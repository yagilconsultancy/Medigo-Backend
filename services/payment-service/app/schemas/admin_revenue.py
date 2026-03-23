from pydantic import BaseModel


class RevenueKPIsResponse(BaseModel):
    total_revenue: float
    avg_revenue: float
    avg_label: str
    peak_period: str
    growth_rate: float


class RevenueTrendPoint(BaseModel):
    label: str
    revenue: float
    count: int


class RevenueByRideTypeItem(BaseModel):
    ride_type: str
    display_name: str
    revenue: float


class RevenueByCityItem(BaseModel):
    city: str
    revenue: float
    rank: int


class RevenueDistributionResponse(BaseModel):
    gross_revenue: float
    platform_commission: float
    driver_payouts: float
    fleet_payouts: float
    refunds_issued: float
