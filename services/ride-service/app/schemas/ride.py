from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, Field


# ---- Request Schemas ----

class CreateRideRequest(BaseModel):
    ride_type: str
    trip_type: str = "transport_only"
    trip_structure: str = "one_way"
    pickup_address: str
    pickup_latitude: float | None = None
    pickup_longitude: float | None = None
    destination_address: str
    destination_latitude: float | None = None
    destination_longitude: float | None = None
    scheduled_at: datetime
    passenger_id: UUID | None = None
    visit_type: str | None = None
    appointment_time: datetime | None = None
    facility_name: str | None = None
    special_instructions: str | None = None
    mobility_level: str | None = None
    assistance_level: str | None = None
    estimated_distance_miles: float | None = None
    estimated_duration_minutes: int | None = None
    estimated_fare: float | None = None
    business_id: UUID | None = None


class StatusTransitionRequest(BaseModel):
    status: str
    notes: str | None = None


class CancelRideRequest(BaseModel):
    reason: str


class RebookRideRequest(BaseModel):
    scheduled_at: datetime


class CreateRecurringRideRequest(BaseModel):
    frequency: str
    pickup_address: str
    destination_address: str
    ride_type: str
    scheduled_time: time
    days_of_week: list[int] | None = None
    start_date: date
    end_date: date | None = None


# ---- Response Schemas ----

class RideResponse(BaseModel):
    id: UUID
    rider_id: UUID
    driver_id: UUID | None = None
    business_id: UUID | None = None
    ride_type: str
    trip_type: str
    trip_structure: str
    pickup_address: str
    destination_address: str
    scheduled_at: datetime
    status: str
    estimated_distance_miles: float | None = None
    estimated_duration_minutes: int | None = None
    estimated_fare: float | None = None
    final_fare: float | None = None
    special_instructions: str | None = None
    visit_type: str | None = None
    facility_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RideDetailResponse(BaseModel):
    id: UUID
    rider_id: UUID
    driver_id: UUID | None = None
    business_id: UUID | None = None
    ride_type: str
    trip_type: str
    trip_structure: str
    pickup_address: str
    pickup_latitude: float | None = None
    pickup_longitude: float | None = None
    destination_address: str
    destination_latitude: float | None = None
    destination_longitude: float | None = None
    scheduled_at: datetime
    pickup_at: datetime | None = None
    dropoff_at: datetime | None = None
    status: str
    estimated_distance_miles: float | None = None
    actual_distance_miles: float | None = None
    estimated_duration_minutes: int | None = None
    actual_duration_minutes: int | None = None
    estimated_fare: float | None = None
    final_fare: float | None = None
    visit_type: str | None = None
    appointment_time: datetime | None = None
    facility_name: str | None = None
    special_instructions: str | None = None
    mobility_level: str | None = None
    assistance_level: str | None = None
    cancellation_reason: str | None = None
    cancelled_at: datetime | None = None
    created_at: datetime

    # Enriched fields
    rider_name: str
    rider_rating: float
    rider_trip_count: int
    driver_rating: "RatingResponse | None" = None
    rider_rating_given: "RatingResponse | None" = None
    timeline: list["StatusLogResponse"] = []

    model_config = {"from_attributes": True}


class StatusLogResponse(BaseModel):
    from_status: str | None = None
    to_status: str
    timestamp: datetime
    notes: str | None = None

    model_config = {"from_attributes": True}


class DriverStatsResponse(BaseModel):
    total_trips: int
    hours_online: float
    average_earnings: float
    rating: float
    earnings_today: float


class RideRequestResponse(BaseModel):
    id: UUID
    ride_id: UUID
    driver_id: UUID
    status: str
    rider_name: str
    rider_rating: float
    pickup_address: str
    destination_address: str
    ride_type: str
    estimated_fare: float | None = None
    estimated_distance_miles: float | None = None
    expires_at: datetime

    model_config = {"from_attributes": True}


class ShareRideResponse(BaseModel):
    ride_id: UUID
    share_token: str
    share_url: str


class DriverContactResponse(BaseModel):
    driver_id: str
    first_name: str
    last_name: str
    phone: str | None = None
    avatar_url: str | None = None
    rating: float
    vehicle_type: str | None = None
    vehicle_make: str | None = None
    vehicle_model: str | None = None
    vehicle_plate: str | None = None
    vehicle_color: str | None = None


class SharedRideResponse(BaseModel):
    id: UUID
    ride_type: str
    pickup_address: str
    destination_address: str
    pickup_latitude: float | None = None
    pickup_longitude: float | None = None
    destination_latitude: float | None = None
    destination_longitude: float | None = None
    scheduled_at: datetime
    status: str
    driver_id: UUID | None = None

    model_config = {"from_attributes": True}


class RecurringRideResponse(BaseModel):
    id: UUID
    rider_id: UUID
    frequency: str
    pickup_address: str
    destination_address: str
    ride_type: str
    scheduled_time: time
    days_of_week: list[int] | None = None
    start_date: date
    end_date: date | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# Import for forward reference
from app.schemas.rating import RatingResponse  # noqa: E402

RideDetailResponse.model_rebuild()
