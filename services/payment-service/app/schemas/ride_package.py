import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PackageKPIs(BaseModel):
    active_count: int = 0
    total_subscribers: int = 0
    type_count: int = 0


class RidePackageResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    package_type: str
    price: Decimal
    ride_count: int | None = None
    is_unlimited: bool
    discount_percent: Decimal
    validity_days: int
    is_active: bool
    active_subscribers: int
    sort_order: int
    created_at: datetime
    updated_at: datetime


class RidePackageListResponse(BaseModel):
    packages: list[RidePackageResponse]


class RidePackageCreate(BaseModel):
    name: str
    description: str | None = None
    package_type: str
    price: Decimal
    ride_count: int | None = None
    is_unlimited: bool = False
    discount_percent: Decimal = Decimal("0")
    validity_days: int = 30
    sort_order: int = 0


class RidePackageUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    package_type: str | None = None
    price: Decimal | None = None
    ride_count: int | None = None
    is_unlimited: bool | None = None
    discount_percent: Decimal | None = None
    validity_days: int | None = None
    sort_order: int | None = None
