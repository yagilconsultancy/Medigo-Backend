import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CommissionKPIs(BaseModel):
    platform_percent: Decimal = Decimal("0")
    driver_percent: Decimal = Decimal("0")
    fleet_percent: Decimal = Decimal("0")
    caregiver_percent: Decimal = Decimal("0")
    reserve_percent: Decimal = Decimal("0")


class CommissionConfigResponse(BaseModel):
    id: uuid.UUID
    platform_percent: Decimal
    driver_percent: Decimal
    fleet_percent: Decimal
    caregiver_percent: Decimal
    reserve_percent: Decimal
    is_active: bool
    version: int
    created_at: datetime


class CommissionConfigUpdate(BaseModel):
    platform_percent: Decimal
    driver_percent: Decimal
    fleet_percent: Decimal
    caregiver_percent: Decimal
    reserve_percent: Decimal
