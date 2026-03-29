from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AlertKPIs(BaseModel):
    active: int = 0
    route_deviations: int = 0
    late_arrivals: int = 0
    resolved_today: int = 0


class SafetyAlertResponse(BaseModel):
    id: UUID
    alert_number: int
    category: str
    severity: str
    description: str
    driver_id: UUID | None = None
    driver_name: str | None = None
    ride_id: UUID | None = None
    trip_display_id: str | None = None
    city: str | None = None
    status: str
    acknowledged_at: datetime | None = None
    acknowledged_by: UUID | None = None
    resolved_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    items: list[SafetyAlertResponse]
    total: int
    page: int
    page_size: int
