from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PricingDashboardKPIs(BaseModel):
    monthly_revenue: Decimal = Decimal("0")
    avg_trip_fare: Decimal = Decimal("0")
    active_service_types: int = 0
    premium_ride_percent: Decimal = Decimal("0")


class RouteComparisonRow(BaseModel):
    route: str
    standard: Decimal | None = None
    wheelchair_wav: Decimal | None = None
    stretcher: Decimal | None = None


class RouteComparisonResponse(BaseModel):
    routes: list[RouteComparisonRow]


class RecentChangeItem(BaseModel):
    log_number: int
    admin_name: str
    category: str
    change_description: str
    created_at: datetime


class RecentChangesResponse(BaseModel):
    changes: list[RecentChangeItem]


class HealthCheckItem(BaseModel):
    label: str
    status: str  # "ok", "warning", "error"
    detail: str | None = None


class PricingHealthResponse(BaseModel):
    items: list[HealthCheckItem]
