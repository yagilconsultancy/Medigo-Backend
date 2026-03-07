from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.safety_report import SafetyReport
from app.models.vehicle_checklist import VehicleChecklist
from app.repositories.safety_report_repo import SafetyReportRepository
from app.repositories.vehicle_checklist_repo import VehicleChecklistRepository
from app.schemas.safety import (
    CreateSafetyReportRequest,
    SafetyReportResponse,
    SubmitVehicleChecklistRequest,
    VehicleChecklistResponse,
)
from mediride_common.auth.dependencies import get_current_user, require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import PaginatedResponse, StandardResponse
from mediride_common.utils import utc_now

router = APIRouter(prefix="/safety")


@router.post("/reports", response_model=StandardResponse[SafetyReportResponse])
async def create_safety_report(
    body: CreateSafetyReportRequest,
    user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = SafetyReportRepository(session)
    report = SafetyReport(
        reporter_id=user.id,
        reported_user_id=body.reported_user_id,
        ride_id=body.ride_id,
        report_type=body.report_type,
        description=body.description,
    )
    report = await repo.create(report)
    return StandardResponse(
        data=SafetyReportResponse.model_validate(report),
        message="Safety report submitted",
    )


@router.get("/reports", response_model=PaginatedResponse[SafetyReportResponse])
async def list_my_safety_reports(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = SafetyReportRepository(session)
    offset = (page - 1) * limit
    reports, total = await repo.get_by_user(user.id, offset, limit)
    return PaginatedResponse(
        data=[SafetyReportResponse.model_validate(r) for r in reports],
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.post("/vehicle-checklist", response_model=StandardResponse[VehicleChecklistResponse])
async def submit_vehicle_checklist(
    body: SubmitVehicleChecklistRequest,
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    session: AsyncSession = Depends(get_db),
):
    repo = VehicleChecklistRepository(session)
    today = utc_now().date()

    # Check if already submitted today
    existing = await repo.get_by_driver_date(user.id, today)
    if existing:
        return StandardResponse(
            data=VehicleChecklistResponse.model_validate(existing),
            message="Checklist already submitted today",
        )

    required_checks = [
        body.tires_ok, body.brakes_ok, body.lights_ok,
        body.fluid_levels_ok, body.first_aid_kit_ok,
        body.fire_extinguisher_ok, body.vehicle_clean,
    ]
    all_passed = all(required_checks)

    checklist = VehicleChecklist(
        driver_id=user.id,
        checklist_date=today,
        tires_ok=body.tires_ok,
        brakes_ok=body.brakes_ok,
        lights_ok=body.lights_ok,
        fluid_levels_ok=body.fluid_levels_ok,
        wheelchair_ramp_ok=body.wheelchair_ramp_ok,
        stretcher_mount_ok=body.stretcher_mount_ok,
        first_aid_kit_ok=body.first_aid_kit_ok,
        fire_extinguisher_ok=body.fire_extinguisher_ok,
        vehicle_clean=body.vehicle_clean,
        all_passed=all_passed,
    )
    checklist = await repo.create(checklist)
    return StandardResponse(
        data=VehicleChecklistResponse.model_validate(checklist),
        message="Vehicle checklist submitted",
    )


@router.get("/vehicle-checklist", response_model=StandardResponse[list[VehicleChecklistResponse]])
async def get_vehicle_checklists(
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    session: AsyncSession = Depends(get_db),
):
    repo = VehicleChecklistRepository(session)
    checklists = await repo.get_recent_by_driver(user.id)
    return StandardResponse(
        data=[VehicleChecklistResponse.model_validate(c) for c in checklists],
    )
