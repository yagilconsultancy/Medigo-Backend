from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CityCreate(BaseModel):
    name: str = Field(..., max_length=100)
    province: str = Field(..., max_length=50)
    number_of_zones: int = Field(..., ge=1)


class CityUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    province: str | None = Field(None, max_length=50)
    number_of_zones: int | None = Field(None, ge=1)
    is_active: bool | None = None


class CityKPIs(BaseModel):
    active_cities: int
    total_zones: int
    cities_online: int
    inactive_cities: int


class CityRow(BaseModel):
    id: UUID
    name: str
    province: str
    service_zones: int
    drivers: int
    riders: int
    total_trips: int
    is_active: bool

    model_config = {"from_attributes": True}


class CityResponse(BaseModel):
    id: UUID
    name: str
    province: str
    number_of_zones: int
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
