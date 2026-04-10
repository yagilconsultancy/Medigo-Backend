from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RideTypeCreate(BaseModel):
    service_type: str = Field(..., max_length=30)
    display_name: str = Field(..., max_length=100)
    description: str | None = None
    base_fare: float = Field(..., ge=0)
    per_km_rate: float = Field(..., ge=0)
    per_min_rate: float = Field(..., ge=0)
    min_fare: float = Field(..., ge=0)


class RideTypeUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=100)
    description: str | None = None
    base_fare: float | None = Field(None, ge=0)
    per_km_rate: float | None = Field(None, ge=0)
    per_min_rate: float | None = Field(None, ge=0)
    min_fare: float | None = Field(None, ge=0)
    is_active: bool | None = None


class RideTypeKPIs(BaseModel):
    total_ride_types: int
    active: int
    inactive: int
    avg_base_fare: float


class RideTypeResponse(BaseModel):
    id: UUID
    service_type: str
    display_name: str
    description: str | None = None
    base_fare: float
    per_km_rate: float
    per_min_rate: float
    min_fare: float
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
