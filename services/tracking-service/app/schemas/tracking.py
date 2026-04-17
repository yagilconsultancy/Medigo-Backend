from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TrackingSessionResponse(BaseModel):
    id: UUID
    ride_id: UUID
    driver_id: UUID
    rider_id: UUID
    status: str
    current_latitude: float | None = None
    current_longitude: float | None = None
    current_heading: float | None = None
    current_speed: float | None = None
    eta_minutes: float | None = None
    distance_remaining_miles: float | None = None
    pickup_latitude: float
    pickup_longitude: float
    destination_latitude: float
    destination_longitude: float
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LocationHistoryEntry(BaseModel):
    id: UUID
    latitude: float
    longitude: float
    heading: float | None = None
    speed: float | None = None
    recorded_at: datetime

    model_config = {"from_attributes": True}


class LocationHistoryResponse(BaseModel):
    ride_id: UUID
    session_id: UUID
    entries: list[LocationHistoryEntry]
    total: int


class LocationUpdateRequest(BaseModel):
    latitude: float
    longitude: float
    heading: float | None = None
    speed: float | None = None


class SimulateLocationUpdateRequest(BaseModel):
    """Public test endpoint schema for simulating driver location updates."""
    driver_id: UUID
    latitude: float
    longitude: float
    heading: float | None = None
    speed: float | None = None
