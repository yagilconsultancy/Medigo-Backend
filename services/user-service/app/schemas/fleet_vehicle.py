from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class VehicleCreate(BaseModel):
    business_id: UUID
    vehicle_name: str | None = Field(None, max_length=255)
    make: str = Field(..., max_length=100)
    model: str = Field(..., max_length=100)
    year: int = Field(..., ge=1900, le=2030)
    plate_number: str = Field(..., max_length=20)
    color: str | None = Field(None, max_length=50)
    vin: str | None = Field(None, max_length=17)
    category: str = Field(...)
    mileage: int | None = None
    insurance_expiry: date | None = None
    registration_expiry: date | None = None


class VehicleUpdate(BaseModel):
    vehicle_name: str | None = Field(None, max_length=255)
    make: str | None = Field(None, max_length=100)
    model: str | None = Field(None, max_length=100)
    year: int | None = Field(None, ge=1900, le=2030)
    plate_number: str | None = Field(None, max_length=20)
    color: str | None = Field(None, max_length=50)
    vin: str | None = Field(None, max_length=17)
    category: str | None = None
    mileage: int | None = None
    insurance_expiry: date | None = None
    registration_expiry: date | None = None


class ChangeVehicleStatusRequest(BaseModel):
    status: str


class AssignDriverToVehicleRequest(BaseModel):
    driver_id: UUID


class ScheduleMaintenanceRequest(BaseModel):
    scheduled_date: date
    notes: str | None = None


class MaintenanceLogResponse(BaseModel):
    id: UUID
    scheduled_date: date
    completed_date: date | None = None
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class VehicleResponse(BaseModel):
    id: UUID
    business_id: UUID
    driver_profile_id: UUID | None = None
    vehicle_name: str | None = None
    make: str
    model: str
    year: int
    plate_number: str
    color: str | None = None
    vin: str | None = None
    category: str
    status: str
    photo_url: str | None = None
    mileage: int | None = None
    insurance_expiry: date | None = None
    registration_expiry: date | None = None
    created_at: datetime
    business_name: str | None = None
    driver_name: str | None = None

    model_config = {"from_attributes": True}


class VehicleDetailResponse(VehicleResponse):
    maintenance_logs: list[MaintenanceLogResponse] = []


class VehicleKPIs(BaseModel):
    total_vehicles: int
    active: int
    maintenance: int
    inactive: int
