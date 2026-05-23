from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, Field

from mediride_common.schemas.enums import (
    RideType,
    RecurringFrequency,
    TripStructure,
    TripType,
)


# ---- Request Schemas ----

class CreateRideRequest(BaseModel):
    ride_type: RideType
    trip_type: TripType = TripType.TRANSPORT_ONLY
    trip_structure: TripStructure = TripStructure.ONE_WAY
    pickup_address: str
    pickup_latitude: float | None = None
    pickup_longitude: float | None = None
    destination_address: str
    destination_latitude: float | None = None
    destination_longitude: float | None = None
    scheduled_at: datetime
    passenger_id: UUID | None = None
    passenger_first_name: str | None = Field(None, min_length=1, max_length=100)
    passenger_last_name: str | None = Field(None, min_length=1, max_length=100)
    passenger_phone: str | None = Field(None, min_length=7, max_length=20)
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
    use_highway_407: bool = False
    highway_407_route: str | None = None
    is_dialysis_trip: bool = False
    booking_channel: str = "mobile_app"
    recurring_frequency: RecurringFrequency | None = None
    recurring_days_of_week: list[int] | None = None
    recurring_end_date: date | None = None


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
    ride_type: RideType
    scheduled_time: time
    days_of_week: list[int] | None = None
    start_date: date
    end_date: date | None = None


# Admin request schemas

class AdminAssignDriverRequest(BaseModel):
    driver_id: UUID


# ---- Response Schemas ----

class RideResponse(BaseModel):
    id: UUID
    rider_id: UUID
    driver_id: UUID | None = None
    caregiver_id: UUID | None = None
    business_id: UUID | None = None
    ride_type: str
    trip_type: str
    trip_structure: str
    pickup_address: str
    destination_address: str
    scheduled_at: datetime
    status: str
    passenger_id: UUID | None = None
    passenger_first_name: str | None = None
    passenger_last_name: str | None = None
    passenger_phone: str | None = None
    estimated_distance_miles: float | None = None
    estimated_duration_minutes: int | None = None
    estimated_fare: float | None = None
    final_fare: float | None = None
    fare_estimate_details: dict | None = None
    special_instructions: str | None = None
    visit_type: str | None = None
    facility_name: str | None = None
    booking_channel: str = "mobile_app"
    facility_id: UUID | None = None
    guest_session_id: UUID | None = None
    recurring_ride_id: UUID | None = None
    use_highway_407: bool = False
    highway_407_route: str | None = None
    is_dialysis_trip: bool = False
    created_at: datetime
    rider_name: str | None = None  # Enriched field for admin endpoints

    # Enriched driver fields for rider endpoints
    driver_name: str | None = None
    driver_phone: str | None = None
    driver_avatar_url: str | None = None
    driver_rating: float | None = None
    driver_vehicle_type: str | None = None
    driver_vehicle_make: str | None = None
    driver_vehicle_model: str | None = None
    driver_vehicle_color: str | None = None
    driver_vehicle_plate: str | None = None

    model_config = {"from_attributes": True}


class RideDetailResponse(BaseModel):
    id: UUID
    rider_id: UUID
    driver_id: UUID | None = None
    caregiver_id: UUID | None = None
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
    passenger_id: UUID | None = None
    passenger_first_name: str | None = None
    passenger_last_name: str | None = None
    passenger_phone: str | None = None
    estimated_distance_miles: float | None = None
    actual_distance_miles: float | None = None
    estimated_duration_minutes: int | None = None
    actual_duration_minutes: int | None = None
    estimated_fare: float | None = None
    final_fare: float | None = None
    fare_estimate_details: dict | None = None
    visit_type: str | None = None
    appointment_time: datetime | None = None
    facility_name: str | None = None
    booking_channel: str = "mobile_app"
    facility_id: UUID | None = None
    guest_session_id: UUID | None = None
    recurring_ride_id: UUID | None = None
    special_instructions: str | None = None
    mobility_level: str | None = None
    assistance_level: str | None = None
    cancellation_reason: str | None = None
    cancelled_at: datetime | None = None
    use_highway_407: bool = False
    highway_407_route: str | None = None
    is_dialysis_trip: bool = False
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


class RiderHistorySummaryResponse(BaseModel):
    total_rides: int
    completed_rides: int
    cancelled_rides: int
    miles_traveled: float


class RiderStatsResponse(BaseModel):
    total_rides: int
    miles_traveled: float
    average_rating_given: float
    member_since: str | None = None


class RiderHistoryOverviewResponse(BaseModel):
    summary: RiderHistorySummaryResponse
    rides: list[RideResponse]
    filtered_total: int
    page: int
    limit: int
    total_pages: int
    status_filter: str = "all"


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
