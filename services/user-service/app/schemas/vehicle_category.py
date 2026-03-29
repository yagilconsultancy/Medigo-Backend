from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class VehicleCategoryConfigResponse(BaseModel):
    id: UUID
    category: str
    display_name: str
    base_fare: Decimal
    per_km_rate: Decimal
    requirements: list[str] = []
    common_vehicles: list[str] = []
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VehicleCategoryConfigUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=100)
    base_fare: Decimal | None = Field(None, ge=0)
    per_km_rate: Decimal | None = Field(None, ge=0)
    requirements: list[str] | None = None
    common_vehicles: list[str] | None = None
    is_active: bool | None = None


class CategoryBreakdownItem(BaseModel):
    category: str
    display_name: str
    count: int
    percentage: float


class VehicleCategoryFleetComposition(BaseModel):
    total_vehicles: int
    breakdown: list[CategoryBreakdownItem]
