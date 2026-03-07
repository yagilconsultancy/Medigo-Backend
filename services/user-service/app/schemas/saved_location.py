from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from mediride_common.schemas.enums import LocationType


class CreateSavedLocationRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)
    location_type: LocationType
    address: str = Field(..., min_length=1, max_length=500)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    place_id: str | None = Field(None, max_length=300)
    notes: str | None = Field(None, max_length=1000)
    is_default: bool = False


class UpdateSavedLocationRequest(BaseModel):
    label: str | None = Field(None, min_length=1, max_length=100)
    location_type: LocationType | None = None
    address: str | None = Field(None, min_length=1, max_length=500)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    place_id: str | None = Field(None, max_length=300)
    notes: str | None = Field(None, max_length=1000)
    is_default: bool | None = None


class ReorderLocationsRequest(BaseModel):
    location_ids: list[UUID]


class SavedLocationResponse(BaseModel):
    id: UUID
    label: str
    location_type: str
    address: str
    latitude: float | None = None
    longitude: float | None = None
    place_id: str | None = None
    notes: str | None = None
    is_default: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
