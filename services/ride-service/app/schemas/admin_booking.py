from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ==================== Request Schemas ====================

class CreateAdminNoteRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    author_type: str = "admin"


class ApproveBookingRequest(BaseModel):
    notes: str | None = None


class DeclineBookingRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class ReassignDriverRequest(BaseModel):
    driver_id: UUID
    reason: str | None = None


class AssignDriverRequest(BaseModel):
    driver_id: UUID


class AssignCaregiverRequest(BaseModel):
    caregiver_id: UUID


class CancelTripRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class ChangeStatusRequest(BaseModel):
    status: str = Field(..., min_length=1, max_length=40)
    notes: str | None = Field(None, max_length=500)


class UpdateBookingRequest(BaseModel):
    """Admin edit of a booking's trip and medical details.

    All fields are optional; only the ones provided are updated.
    """

    # Locations
    pickup_address: str | None = Field(None, min_length=1)
    pickup_latitude: float | None = None
    pickup_longitude: float | None = None
    destination_address: str | None = Field(None, min_length=1)
    destination_latitude: float | None = None
    destination_longitude: float | None = None

    # Scheduling
    scheduled_at: datetime | None = None

    # Classification
    ride_type: str | None = Field(None, max_length=20)
    trip_type: str | None = Field(None, max_length=30)
    trip_structure: str | None = Field(None, max_length=20)

    # Medical / passenger info
    visit_type: str | None = Field(None, max_length=100)
    facility_name: str | None = Field(None, max_length=255)
    mobility_level: str | None = Field(None, max_length=30)
    assistance_level: str | None = Field(None, max_length=30)
    special_instructions: str | None = None
    passenger_first_name: str | None = Field(None, max_length=100)
    passenger_last_name: str | None = Field(None, max_length=100)
    passenger_phone: str | None = Field(None, max_length=20)


# ==================== Response Schemas ====================

class AdminNoteResponse(BaseModel):
    id: UUID
    ride_id: UUID
    author_id: UUID | None = None
    author_type: str
    author_name: str | None = None
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StatusLogEntry(BaseModel):
    from_status: str | None = None
    to_status: str
    timestamp: datetime
    notes: str | None = None
    changed_by: UUID | None = None

    model_config = {"from_attributes": True}


class FareBreakdownDetail(BaseModel):
    base_fare: float | None = None
    distance_charge: float | None = None
    wait_time_charge: float | None = None
    surcharges_capped: float | None = None
    highway_407_toll: float | None = None
    insurance_gateway_fee: float | None = None
    total_fare: float | None = None
    driver_earnings: float | None = None
    payment_method: str | None = None


# ---- Pending Bookings ----

class PendingBookingsKPIs(BaseModel):
    pending_now: int
    avg_wait_minutes: int
    assigned_count: int


class PendingBookingResponse(BaseModel):
    id: UUID
    rider_id: UUID
    rider_name: str = "Unknown"
    rider_phone: str | None = None
    ride_type: str
    trip_type: str
    trip_structure: str
    pickup_address: str
    destination_address: str
    scheduled_at: datetime
    created_at: datetime
    wait_minutes: int = 0
    special_instructions: str | None = None
    mobility_level: str | None = None
    assistance_level: str | None = None
    recurring_ride_id: UUID | None = None
    is_recurring: bool = False

    model_config = {"from_attributes": True}


# ---- Scheduled Trips ----

class ScheduledTripsKPIs(BaseModel):
    upcoming_count: int
    recurring_count: int
    needs_assignment_count: int


class ScheduledTripResponse(BaseModel):
    id: UUID
    rider_id: UUID
    rider_name: str = "Unknown"
    ride_type: str
    trip_type: str
    pickup_address: str
    destination_address: str
    scheduled_at: datetime
    status: str
    driver_id: UUID | None = None
    driver_name: str | None = None
    recurring_ride_id: UUID | None = None
    is_recurring: bool = False
    recurring_days: list[int] | None = None
    recurring_frequency: str | None = None

    model_config = {"from_attributes": True}


# ---- Cancelled Trips ----

class CancelledTripsKPIs(BaseModel):
    total_cancelled: int
    no_show_count: int
    refunds_pending: int
    refunds_processed: int


class CancelledTripResponse(BaseModel):
    id: UUID
    rider_id: UUID
    rider_name: str = "Unknown"
    pickup_address: str
    destination_address: str
    scheduled_at: datetime
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None
    cancelled_by: UUID | None = None
    cancelled_by_name: str | None = None
    status: str
    driver_id: UUID | None = None
    driver_name: str | None = None
    final_fare: float | None = None
    refund_status: str | None = None
    refund_amount: float | None = None

    model_config = {"from_attributes": True}


# ---- Booking Detail ----

class AdminBookingDetailResponse(BaseModel):
    # Core ride data
    id: UUID
    rider_id: UUID
    driver_id: UUID | None = None
    caregiver_id: UUID | None = None
    business_id: UUID | None = None
    ride_type: str
    trip_type: str
    trip_structure: str
    status: str

    # Locations
    pickup_address: str
    pickup_latitude: float | None = None
    pickup_longitude: float | None = None
    destination_address: str
    destination_latitude: float | None = None
    destination_longitude: float | None = None

    # Timing
    scheduled_at: datetime
    pickup_at: datetime | None = None
    dropoff_at: datetime | None = None
    created_at: datetime

    # Distance & duration
    estimated_distance_miles: float | None = None
    actual_distance_miles: float | None = None
    estimated_duration_minutes: int | None = None
    actual_duration_minutes: int | None = None

    # Fare
    estimated_fare: float | None = None
    final_fare: float | None = None

    # Medical
    special_instructions: str | None = None
    mobility_level: str | None = None
    assistance_level: str | None = None
    visit_type: str | None = None
    facility_name: str | None = None
    appointment_time: datetime | None = None

    # Passenger
    passenger_first_name: str | None = None
    passenger_last_name: str | None = None
    passenger_phone: str | None = None

    # Cancellation
    cancellation_reason: str | None = None
    cancelled_at: datetime | None = None
    cancelled_by: UUID | None = None

    # Flags
    use_highway_407: bool = False
    is_dialysis_trip: bool = False

    # Enriched: Patient info
    rider_name: str = "Unknown"
    rider_phone: str | None = None
    rider_rating: float = 5.0
    rider_trip_count: int = 0

    # Enriched: Caregiver info
    caregiver_name: str | None = None

    # Enriched: Driver info
    driver_name: str | None = None
    driver_phone: str | None = None
    driver_rating: float | None = None
    driver_vehicle_type: str | None = None
    driver_vehicle_make: str | None = None
    driver_vehicle_model: str | None = None
    driver_vehicle_plate: str | None = None
    driver_vehicle_color: str | None = None

    # Enriched: Timeline
    timeline: list[StatusLogEntry] = []

    # Enriched: Admin notes
    admin_notes: list[AdminNoteResponse] = []

    # Enriched: Fare breakdown
    fare_breakdown: FareBreakdownDetail | None = None

    # Recurring info
    recurring_ride_id: UUID | None = None
    is_recurring: bool = False

    # Statuses the admin may transition to from the current status
    allowed_status_transitions: list[str] = []

    model_config = {"from_attributes": True}


# ---- Available Drivers ----

class AvailableDriverResponse(BaseModel):
    driver_id: UUID
    name: str
    phone: str | None = None
    avatar_url: str | None = None
    rating: float = 5.0
    vehicle_type: str | None = None
    vehicle_make: str | None = None
    vehicle_model: str | None = None
    vehicle_plate: str | None = None
