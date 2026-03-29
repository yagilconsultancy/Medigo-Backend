import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class ServiceTypeListItem(BaseModel):
    service_type: str
    display_name: str
    is_active: bool
    sort_order: int


class ServiceTypeListResponse(BaseModel):
    service_types: list[ServiceTypeListItem]


class ServiceTypeConfigResponse(BaseModel):
    id: uuid.UUID
    service_type: str
    display_name: str
    config: dict[str, Any]
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class ServiceTypeConfigUpdate(BaseModel):
    config: dict[str, Any]


class RoutePrice(BaseModel):
    route: str
    distance_km: Decimal
    estimated_fare: Decimal


class RoutePricingResponse(BaseModel):
    service_type: str
    routes: list[RoutePrice]


class RoutePricingUpdate(BaseModel):
    routes: dict[str, dict[str, Any]]


class CommissionViewResponse(BaseModel):
    service_type: str
    platform_commission: Decimal
    driver_share: Decimal
    fleet_share: Decimal
