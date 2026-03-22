from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ActiveTripKPIs(BaseModel):
    active_trips: int
    arriving_soon: int
    avg_speed: float | None = None
    completed_today: int


class LocationPoint(BaseModel):
    latitude: float
    longitude: float
    heading: float | None = None
    speed: float | None = None
    recorded_at: datetime

    model_config = {"from_attributes": True}


class ActiveTripOverview(BaseModel):
    session_id: UUID
    ride_id: UUID
    trip_id_display: str  # "TR-XXXX"
    status: str  # transit / arriving / completed

    # Driver info
    driver_id: UUID
    driver_name: str | None = None
    driver_avatar: str | None = None
    driver_vehicle: str | None = None

    # Rider info
    rider_id: UUID
    patient_name: str | None = None

    # Current position
    current_latitude: float | None = None
    current_longitude: float | None = None
    current_heading: float | None = None
    current_speed: float | None = None

    # ETA & progress
    eta_minutes: float | None = None
    distance_remaining: float | None = None
    progress_percent: float | None = None

    # Route endpoints
    pickup_address: str | None = None
    pickup_latitude: float | None = None
    pickup_longitude: float | None = None
    destination_address: str | None = None
    destination_latitude: float | None = None
    destination_longitude: float | None = None

    # Ride details
    ride_type: str | None = None
    medical_alerts: list[str] = []

    # Timing
    started_at: datetime | None = None
    elapsed_minutes: float | None = None


class ActiveTripDetail(ActiveTripOverview):
    special_instructions: str | None = None
    mobility_level: str | None = None
    estimated_distance: float | None = None
    estimated_duration: int | None = None
    driver_rating: float | None = None
    driver_phone: str | None = None
    route_history: list[LocationPoint] = []


class LiveDriverEntry(BaseModel):
    driver_id: UUID
    driver_name: str | None = None
    driver_avatar: str | None = None
    driver_vehicle: str | None = None

    # Current position
    current_latitude: float | None = None
    current_longitude: float | None = None
    current_heading: float | None = None
    current_speed: float | None = None

    # Active ride info
    ride_id: UUID | None = None
    trip_id_display: str | None = None
    trip_status: str | None = None
    eta_minutes: float | None = None
    pickup_address: str | None = None
    destination_address: str | None = None
