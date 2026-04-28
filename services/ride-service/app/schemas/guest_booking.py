from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.ride import CreateRideRequest, RideResponse


class CreateGuestSessionRequest(BaseModel):
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, min_length=10, max_length=20)
    full_name: str | None = Field(None, min_length=1, max_length=200)
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_contact(self):
        if not self.email and not self.phone:
            raise ValueError("Either email or phone is required")
        if self.full_name and not (self.first_name and self.last_name):
            parts = self.full_name.strip().split(None, 1)
            self.first_name = self.first_name or parts[0]
            self.last_name = self.last_name or (parts[1] if len(parts) > 1 else "")
        return self


class CreateGuestBookingRequest(CreateRideRequest):
    session_id: UUID


class GuestBookingAccessResponse(BaseModel):
    ride: RideResponse
    share_token: str | None = None
    share_url: str | None = None


class GuestSessionResponse(BaseModel):
    session_id: UUID
    rider_id: UUID
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    is_guest: bool = True
    created_at: datetime
    updated_at: datetime
    current_booking: GuestBookingAccessResponse | None = None


class GuestBookingResponse(BaseModel):
    session_id: UUID
    rider_id: UUID
    is_guest: bool = True
    booking: GuestBookingAccessResponse
