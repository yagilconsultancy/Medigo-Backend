from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.fleet_application import FleetDocumentResponse


class FleetCompanyResponse(BaseModel):
    id: UUID
    name: str
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    state: str | None = None
    logo_url: str | None = None
    is_active: bool
    vehicle_count: int = 0
    driver_count: int = 0
    revenue: float = 0.0
    created_at: datetime


class FleetCompanyKPIs(BaseModel):
    total_fleets: int
    active_fleets: int
    total_fleet_vehicles: int
    fleet_drivers: int


class FleetCompanyDetailResponse(BaseModel):
    id: UUID
    name: str
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    address: str | None = None
    logo_url: str | None = None
    is_active: bool
    vehicle_count: int = 0
    driver_count: int = 0
    total_revenue: float = 0.0
    avg_rating: float = 0.0
    documents: list[FleetDocumentResponse] = []
    created_at: datetime
    updated_at: datetime


class AddFleetPartnerRequest(BaseModel):
    name: str = Field(..., max_length=255)
    contact_person: str = Field(..., max_length=255)
    email: str = Field(..., max_length=255)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=50)
    num_vehicles: int = Field(0, ge=0)
    num_drivers: int = Field(0, ge=0)


class UpdateFleetProfileRequest(BaseModel):
    name: str | None = Field(None, max_length=255)
    contact_person: str | None = Field(None, max_length=255)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=20)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=50)


class ToggleStatusRequest(BaseModel):
    is_active: bool
