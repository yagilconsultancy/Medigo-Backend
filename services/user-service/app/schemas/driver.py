from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


class DriverProfileResponse(BaseModel):
    user_id: UUID
    business_id: UUID
    license_number: str | None = None
    license_expiry: date | None = None
    vehicle_type: str | None = None
    vehicle_make: str | None = None
    vehicle_model: str | None = None
    vehicle_year: int | None = None
    vehicle_plate: str | None = None
    vehicle_color: str | None = None
    vehicle_vin: str | None = None
    vehicle_photo_url: str | None = None
    vehicle_verified: bool = False
    background_check_status: str
    is_approved: bool
    is_online: bool
    rating: float
    total_trips: int

    model_config = {"from_attributes": True}


class UpdateDriverProfileRequest(BaseModel):
    license_number: str | None = Field(None, max_length=50)
    license_expiry: date | None = None
    vehicle_type: str | None = Field(None, max_length=50)
    vehicle_make: str | None = Field(None, max_length=100)
    vehicle_model: str | None = Field(None, max_length=100)
    vehicle_year: int | None = None
    vehicle_plate: str | None = Field(None, max_length=20)
    vehicle_color: str | None = Field(None, max_length=50)
    vehicle_vin: str | None = Field(None, max_length=17)


class DriverStatusRequest(BaseModel):
    is_online: bool


class VehicleDetailsResponse(BaseModel):
    vehicle_type: str | None = None
    vehicle_make: str | None = None
    vehicle_model: str | None = None
    vehicle_year: int | None = None
    vehicle_plate: str | None = None
    vehicle_color: str | None = None
    vehicle_vin: str | None = None
    vehicle_photo_url: str | None = None
    vehicle_verified: bool = False

    model_config = {"from_attributes": True}


class UpdateVehicleRequest(BaseModel):
    vehicle_type: str | None = Field(None, max_length=50)
    vehicle_make: str | None = Field(None, max_length=100)
    vehicle_model: str | None = Field(None, max_length=100)
    vehicle_year: int | None = None
    vehicle_plate: str | None = Field(None, max_length=20)
    vehicle_color: str | None = Field(None, max_length=50)
    vehicle_vin: str | None = Field(None, max_length=17)
