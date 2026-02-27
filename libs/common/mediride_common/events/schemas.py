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
    role: str
    business_id: UUID | None = None


class UserVerifiedPayload(BaseModel):
    user_id: UUID
    email: str | None = None
    phone: str | None = None


class DriverInviteSentPayload(BaseModel):
    invitation_id: UUID
    business_id: UUID
    business_name: str
    email: str
    invite_token: str


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


class BusinessCreatedPayload(BaseModel):
    business_id: UUID
    name: str
    created_by: UUID


# Ride event payloads
class RideCreatedPayload(BaseModel):
    ride_id: UUID
    rider_id: UUID
    ride_type: str
    pickup_address: str
    destination_address: str
    scheduled_at: datetime
    estimated_cost: float | None = None


class RideStatusChangedPayload(BaseModel):
    ride_id: UUID
    rider_id: UUID
    driver_id: UUID | None = None
    from_status: str | None = None
    to_status: str
    changed_by: UUID | None = None


# Payment event payloads
class PaymentCompletedPayload(BaseModel):
    transaction_id: UUID
    ride_id: UUID
    user_id: UUID
    amount: float
    status: str
