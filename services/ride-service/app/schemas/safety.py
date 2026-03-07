from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateSafetyReportRequest(BaseModel):
    reported_user_id: UUID | None = None
    ride_id: UUID | None = None
    report_type: str
    description: str = Field(..., min_length=10, max_length=2000)


class SafetyReportResponse(BaseModel):
    id: UUID
    reporter_id: UUID
    reported_user_id: UUID | None = None
    ride_id: UUID | None = None
    report_type: str
    description: str
    status: str
    resolution: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SubmitVehicleChecklistRequest(BaseModel):
    tires_ok: bool = False
    brakes_ok: bool = False
    lights_ok: bool = False
    fluid_levels_ok: bool = False
    wheelchair_ramp_ok: bool | None = None
    stretcher_mount_ok: bool | None = None
    first_aid_kit_ok: bool = False
    fire_extinguisher_ok: bool = False
    vehicle_clean: bool = False


class VehicleChecklistResponse(BaseModel):
    id: UUID
    driver_id: UUID
    checklist_date: date
    tires_ok: bool
    brakes_ok: bool
    lights_ok: bool
    fluid_levels_ok: bool
    wheelchair_ramp_ok: bool | None = None
    stretcher_mount_ok: bool | None = None
    first_aid_kit_ok: bool
    fire_extinguisher_ok: bool
    vehicle_clean: bool
    all_passed: bool
    created_at: datetime

    model_config = {"from_attributes": True}
