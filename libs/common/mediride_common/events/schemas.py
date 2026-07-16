from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from mediride_common.utils import generate_uuid, utc_now


class EventEnvelope(BaseModel):
    event_id: UUID = Field(default_factory=generate_uuid)
    event_type: str
    timestamp: datetime = Field(default_factory=utc_now)
    correlation_id: str = ""
    source_service: str = ""
    version: str = "1.0"
    payload: dict


# Auth event payloads
class UserRegisteredPayload(BaseModel):
    user_id: UUID
    email: str | None = None
    phone: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    role: str
    business_id: UUID | None = None


class UserVerifiedPayload(BaseModel):
    user_id: UUID
    email: str | None = None
    phone: str | None = None


class UserOTPRequestedPayload(BaseModel):
    user_id: UUID
    purpose: str
    channel: str
    otp_code: str
    email: str | None = None
    phone: str | None = None


class PasswordResetRequestedPayload(BaseModel):
    user_id: UUID
    email: str
    reset_token: str


class DriverInviteSentPayload(BaseModel):
    invitation_id: UUID
    business_id: UUID
    fleet_name: str
    email: str
    invite_token: str
    temporary_password: str | None = None


class DriverEmailChangedPayload(BaseModel):
    driver_id: UUID
    email: str  # the new email the reactivation message is sent to
    name: str
    reactivation_link: str


class AdminInviteSentPayload(BaseModel):
    invitation_id: UUID
    email: str
    full_name: str
    role_display_name: str
    temporary_password: str
    invited_by_name: str


# User event payloads
class ProfileCreatedPayload(BaseModel):
    user_id: UUID
    role: str
    email: str | None = None
    phone: str | None = None


class DriverApprovedPayload(BaseModel):
    driver_id: UUID
    business_id: UUID
    email: str | None = None


class DriverStatusPayload(BaseModel):
    driver_id: UUID
    is_online: bool
    business_id: UUID


class FleetApplicationCreatedPayload(BaseModel):
    application_id: UUID
    company_name: str
    email: str
    created_by: str


class FleetApplicationInfoRequestedPayload(BaseModel):
    application_id: UUID
    company_name: str
    email: str
    message: str
    requested_by: UUID


class FleetApplicationApprovedPayload(BaseModel):
    application_id: UUID
    fleet_id: UUID
    company_name: str
    email: str
    approved_by: UUID


class FleetApplicationRejectedPayload(BaseModel):
    application_id: UUID
    company_name: str
    email: str
    rejected_by: UUID
    reason: str


class FleetCreatedPayload(BaseModel):
    fleet_id: UUID
    name: str
    created_by: UUID


class DriverDocumentUploadedPayload(BaseModel):
    user_id: UUID
    document_id: UUID
    document_type: str
    business_id: UUID


# Ride event payloads
class RideCreatedPayload(BaseModel):
    ride_id: UUID
    rider_id: UUID
    ride_type: str
    pickup_address: str
    destination_address: str
    scheduled_at: datetime
    estimated_cost: float | None = None

    # Optional booking context, used to build the admin booking alert.
    # All optional so older publishers keep validating.
    trip_type: str | None = None
    trip_structure: str | None = None
    booking_channel: str | None = None
    visit_type: str | None = None
    facility_name: str | None = None
    appointment_time: datetime | None = None
    special_instructions: str | None = None
    is_dialysis_trip: bool | None = None
    passenger_first_name: str | None = None
    passenger_last_name: str | None = None
    passenger_phone: str | None = None
    mobility_level: str | None = None
    assistance_level: str | None = None
    estimated_distance_miles: float | None = None
    estimated_duration_minutes: int | None = None
    currency: str | None = None
    created_at: datetime | None = None
    recurring_ride_id: UUID | None = None
    # True for the future occurrences auto-generated from a recurring series,
    # so consumers can act on the booking once instead of once per occurrence.
    is_recurring_occurrence: bool = False


class RideStatusChangedPayload(BaseModel):
    ride_id: UUID
    rider_id: UUID
    driver_id: UUID | None = None
    from_status: str | None = None
    to_status: str
    changed_by: UUID | None = None


# Ride request payload
class RideRequestPayload(BaseModel):
    ride_id: UUID
    rider_id: UUID
    driver_id: UUID
    pickup_address: str
    destination_address: str
    ride_type: str
    estimated_fare: float
    estimated_distance: float
    rider_name: str
    rider_rating: float


# Rating event payload
class RideRatingSubmittedPayload(BaseModel):
    ride_id: UUID
    rated_user_id: UUID
    rated_by_user_id: UUID
    rating: int
    rating_type: str


# Payment event payloads
class PaymentCompletedPayload(BaseModel):
    transaction_id: UUID
    ride_id: UUID
    user_id: UUID
    amount: float
    status: str


class WithdrawalPayload(BaseModel):
    withdrawal_id: UUID
    driver_id: UUID
    amount: float
    status: str


# Tracking event payloads
class DriverLocationUpdatedPayload(BaseModel):
    driver_id: UUID
    ride_id: UUID | None = None
    latitude: float
    longitude: float
    heading: float | None = None
    speed: float | None = None
    timestamp: datetime = Field(default_factory=utc_now)


class RideETAUpdatedPayload(BaseModel):
    ride_id: UUID
    rider_id: UUID
    driver_id: UUID
    eta_minutes: float
    distance_miles: float


# Chat event payloads
class ChatMessageSentPayload(BaseModel):
    conversation_id: UUID
    message_id: UUID
    sender_id: UUID
    recipient_id: UUID
    ride_id: UUID
    content: str
    message_type: str = "text"
