from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_publisher
from app.repositories.business_repo import BusinessRepository
from app.repositories.driver_repo import DriverRepository
from app.repositories.maintenance_log_repo import VehicleMaintenanceLogRepository
from app.repositories.user_repo import UserRepository
from app.repositories.vehicle_repo import VehicleRepository
from app.schemas.fleet_vehicle import (
    AssignDriverToVehicleRequest,
    ChangeVehicleStatusRequest,
    MaintenanceLogResponse,
    ScheduleMaintenanceRequest,
    VehicleCreate,
    VehicleDetailResponse,
    VehicleKPIs,
    VehicleResponse,
    VehicleUpdate,
)
from app.services.fleet_vehicle_service import FleetVehicleService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import PaginatedResponse, StandardResponse

router = APIRouter()


def _get_service(
    session: AsyncSession = Depends(get_db),
    publisher: EventPublisher = Depends(get_publisher),
) -> FleetVehicleService:
    return FleetVehicleService(
        vehicle_repo=VehicleRepository(session),
        maintenance_repo=VehicleMaintenanceLogRepository(session),
        business_repo=BusinessRepository(session),
        driver_repo=DriverRepository(session),
        user_repo=UserRepository(session),
        publisher=publisher,
    )


# --- Static routes first ---


@router.get(
    "/admin/fleet/vehicles/kpis",
    response_model=StandardResponse[VehicleKPIs],
)
async def get_vehicle_kpis(
    business_id: UUID | None = Query(None),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetVehicleService = Depends(_get_service),
):
    kpis = await service.get_kpis(business_id)
    return StandardResponse(data=kpis)


@router.get(
    "/admin/fleet/vehicles",
    response_model=PaginatedResponse[VehicleResponse],
)
async def list_vehicles(
    business_id: UUID | None = Query(None),
    status: str | None = Query(None),
    category: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetVehicleService = Depends(_get_service),
):
    offset = (page - 1) * limit
    vehicles, total = await service.list_vehicles(
        business_id=business_id,
        status_filter=status,
        category_filter=category,
        search=search,
        offset=offset,
        limit=limit,
    )
    return PaginatedResponse(
        data=vehicles,
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.post(
    "/admin/fleet/vehicles",
    response_model=StandardResponse[VehicleResponse],
    status_code=201,
)
async def create_vehicle(
    body: VehicleCreate,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetVehicleService = Depends(_get_service),
):
    try:
        vehicle = await service.create_vehicle(
            admin_id=user.id,
            **body.model_dump(),
        )
        return StandardResponse(data=vehicle, message="Vehicle registered")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Dynamic routes ---


@router.get(
    "/admin/fleet/vehicles/{vehicle_id}",
    response_model=StandardResponse[VehicleDetailResponse],
)
async def get_vehicle(
    vehicle_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetVehicleService = Depends(_get_service),
):
    try:
        vehicle = await service.get_vehicle(vehicle_id)
        return StandardResponse(data=vehicle)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put(
    "/admin/fleet/vehicles/{vehicle_id}",
    response_model=StandardResponse[VehicleResponse],
)
async def update_vehicle(
    vehicle_id: UUID,
    body: VehicleUpdate,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetVehicleService = Depends(_get_service),
):
    try:
        vehicle = await service.update_vehicle(
            vehicle_id=vehicle_id,
            **body.model_dump(exclude_unset=True),
        )
        return StandardResponse(data=vehicle, message="Vehicle updated")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put(
    "/admin/fleet/vehicles/{vehicle_id}/status",
    response_model=StandardResponse[VehicleResponse],
)
async def change_vehicle_status(
    vehicle_id: UUID,
    body: ChangeVehicleStatusRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetVehicleService = Depends(_get_service),
):
    try:
        vehicle = await service.change_status(
            vehicle_id=vehicle_id,
            new_status=body.status,
            admin_id=user.id,
        )
        return StandardResponse(
            data=vehicle,
            message=f"Vehicle status updated to {body.status}",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/admin/fleet/vehicles/{vehicle_id}/assign-driver",
    response_model=StandardResponse[VehicleResponse],
)
async def assign_driver_to_vehicle(
    vehicle_id: UUID,
    body: AssignDriverToVehicleRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetVehicleService = Depends(_get_service),
):
    try:
        vehicle = await service.assign_driver(
            vehicle_id=vehicle_id,
            driver_id=body.driver_id,
        )
        return StandardResponse(data=vehicle, message="Driver assigned to vehicle")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/admin/fleet/vehicles/{vehicle_id}/unassign-driver",
    response_model=StandardResponse[VehicleResponse],
)
async def unassign_driver_from_vehicle(
    vehicle_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetVehicleService = Depends(_get_service),
):
    try:
        vehicle = await service.unassign_driver(vehicle_id)
        return StandardResponse(data=vehicle, message="Driver unassigned from vehicle")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/admin/fleet/vehicles/{vehicle_id}/maintenance",
    response_model=StandardResponse[MaintenanceLogResponse],
    status_code=201,
)
async def schedule_maintenance(
    vehicle_id: UUID,
    body: ScheduleMaintenanceRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetVehicleService = Depends(_get_service),
):
    try:
        log = await service.schedule_maintenance(
            vehicle_id=vehicle_id,
            scheduled_date=body.scheduled_date,
            admin_id=user.id,
            notes=body.notes,
        )
        return StandardResponse(
            data=MaintenanceLogResponse.model_validate(log),
            message="Maintenance scheduled",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete(
    "/admin/fleet/vehicles/{vehicle_id}",
    response_model=StandardResponse,
)
async def delete_vehicle(
    vehicle_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetVehicleService = Depends(_get_service),
):
    try:
        await service.delete_vehicle(vehicle_id)
        return StandardResponse(message="Vehicle removed")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
