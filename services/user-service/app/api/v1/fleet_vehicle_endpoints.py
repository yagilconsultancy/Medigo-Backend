from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db, get_publisher, get_s3_client
from app.repositories.driver_repo import DriverRepository
from app.repositories.fleet_repo import FleetRepository
from app.repositories.maintenance_log_repo import VehicleMaintenanceLogRepository
from app.repositories.user_repo import UserRepository
from app.repositories.vehicle_category_config_repo import VehicleCategoryConfigRepository
from app.repositories.vehicle_document_repo import VehicleDocumentRepository
from app.repositories.vehicle_repo import VehicleRepository
from app.schemas.fleet_vehicle import (
    AssignDriverToVehicleRequest,
    ChangeVehicleStatusRequest,
    MaintenanceLogResponse,
    ScheduleMaintenanceRequest,
    VehicleCreate,
    VehicleDetailResponse,
    VehicleKPIs,
    VehicleProfileResponse,
    VehicleResponse,
    VehicleUpdate,
)
from app.schemas.vehicle_category import (
    VehicleCategoryConfigResponse,
    VehicleCategoryConfigUpdate,
    VehicleCategoryFleetComposition,
)
from app.schemas.vehicle_document import (
    VehicleDocumentOverview,
    VehicleDocumentResponse,
    VehicleDocumentUploadResponse,
)
from app.services.fleet_vehicle_service import FleetVehicleService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import PaginatedResponse, StandardResponse
from mediride_common.storage.s3_client import S3StorageClient

router = APIRouter()


def _get_service(
    session: AsyncSession = Depends(get_db),
    publisher: EventPublisher = Depends(get_publisher),
) -> FleetVehicleService:
    return FleetVehicleService(
        vehicle_repo=VehicleRepository(session),
        maintenance_repo=VehicleMaintenanceLogRepository(session),
        fleet_repo=FleetRepository(session),
        driver_repo=DriverRepository(session),
        user_repo=UserRepository(session),
        publisher=publisher,
        vehicle_doc_repo=VehicleDocumentRepository(session),
        category_config_repo=VehicleCategoryConfigRepository(session),
    )


# --- Static routes first (before /{vehicle_id}) ---


@router.get(
    "/admin/fleet/vehicles/kpis",
    response_model=StandardResponse[VehicleKPIs],
)
async def get_vehicle_kpis(
    fleet_id: UUID | None = Query(None),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetVehicleService = Depends(_get_service),
):
    kpis = await service.get_kpis(fleet_id)
    return StandardResponse(data=kpis)


@router.get(
    "/admin/fleet/vehicles/documents/overview",
    response_model=StandardResponse[VehicleDocumentOverview],
)
async def get_vehicle_document_overview(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetVehicleService = Depends(_get_service),
):
    """Vehicle documents overview with KPIs and per-vehicle document matrix."""
    result = await service.get_vehicle_document_overview(
        search=search, page=page, limit=limit
    )
    return StandardResponse(data=result)


@router.get(
    "/admin/fleet/vehicles/categories",
    response_model=StandardResponse[list[VehicleCategoryConfigResponse]],
)
async def list_category_configs(
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetVehicleService = Depends(_get_service),
):
    """List all vehicle category configurations with pricing."""
    configs = await service.list_category_configs()
    return StandardResponse(data=configs)


@router.get(
    "/admin/fleet/vehicles/categories/composition",
    response_model=StandardResponse[VehicleCategoryFleetComposition],
)
async def get_fleet_composition(
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetVehicleService = Depends(_get_service),
):
    """Get fleet composition breakdown by vehicle category."""
    composition = await service.get_fleet_composition()
    return StandardResponse(data=composition)


@router.put(
    "/admin/fleet/vehicles/categories/{category}",
    response_model=StandardResponse[VehicleCategoryConfigResponse],
)
async def update_category_config(
    category: str,
    body: VehicleCategoryConfigUpdate,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetVehicleService = Depends(_get_service),
):
    """Update a vehicle category configuration (pricing, requirements)."""
    try:
        config = await service.update_category_config(category, body)
        return StandardResponse(data=config, message="Category config updated")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/admin/fleet/vehicles/profiles",
    response_model=PaginatedResponse[VehicleProfileResponse],
)
async def list_vehicle_profiles(
    search: str | None = Query(None),
    category: str | None = Query(None),
    fleet_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetVehicleService = Depends(_get_service),
):
    """Vehicle profiles with enriched detail (driver, fleet, documents, maintenance)."""
    profiles, total = await service.get_vehicle_profiles(
        search=search, category=category, fleet_id=fleet_id, page=page, limit=limit
    )
    return PaginatedResponse(
        data=profiles,
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.get(
    "/admin/fleet/vehicles",
    response_model=PaginatedResponse[VehicleResponse],
)
async def list_vehicles(
    fleet_id: UUID | None = Query(None),
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
        business_id=fleet_id,
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


@router.get(
    "/admin/fleet/vehicles/{vehicle_id}/documents",
    response_model=StandardResponse[list[VehicleDocumentResponse]],
)
async def get_vehicle_documents(
    vehicle_id: UUID,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetVehicleService = Depends(_get_service),
):
    """Get all documents for a specific vehicle."""
    try:
        docs = await service.get_vehicle_documents(vehicle_id)
        return StandardResponse(data=docs)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/admin/fleet/vehicles/{vehicle_id}/documents",
    response_model=StandardResponse[VehicleDocumentUploadResponse],
    status_code=201,
)
async def upload_vehicle_document(
    vehicle_id: UUID,
    document_type: str = Form(...),
    expires_at: date | None = Form(None),
    notes: str | None = Form(None),
    file: UploadFile = File(...),
    admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetVehicleService = Depends(_get_service),
    s3_client: S3StorageClient = Depends(get_s3_client),
):
    """Upload a document for a vehicle (registration, insurance, inspection)."""
    try:
        file_data = await file.read()
        file_name = file.filename or "unknown"
        mime_type = file.content_type or "application/octet-stream"

        # Upload to S3
        file_key = f"vehicles/{vehicle_id}/documents/{document_type}/{file_name}"
        await s3_client.upload_file(
            bucket=settings.S3_BUCKET_DOCUMENTS,
            key=file_key,
            data=file_data,
            content_type=mime_type,
        )

        doc = await service.upload_vehicle_document(
            vehicle_id=vehicle_id,
            document_type=document_type,
            file_key=file_key,
            file_name=file_name,
            file_size=len(file_data),
            mime_type=mime_type,
            admin_id=admin.id,
            expires_at=expires_at,
            notes=notes,
        )
        return StandardResponse(data=doc, message="Document uploaded")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/admin/fleet/vehicles/{vehicle_id}/documents/{doc_id}/replace",
    response_model=StandardResponse[VehicleDocumentUploadResponse],
)
async def replace_vehicle_document(
    vehicle_id: UUID,
    doc_id: UUID,
    expires_at: date | None = Form(None),
    notes: str | None = Form(None),
    file: UploadFile = File(...),
    admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetVehicleService = Depends(_get_service),
    s3_client: S3StorageClient = Depends(get_s3_client),
):
    """Replace an existing vehicle document with a new file."""
    try:
        file_data = await file.read()
        file_name = file.filename or "unknown"
        mime_type = file.content_type or "application/octet-stream"

        # Upload to S3
        file_key = f"vehicles/{vehicle_id}/documents/replaced/{file_name}"
        await s3_client.upload_file(
            bucket=settings.S3_BUCKET_DOCUMENTS,
            key=file_key,
            data=file_data,
            content_type=mime_type,
        )

        doc = await service.replace_vehicle_document(
            vehicle_id=vehicle_id,
            doc_id=doc_id,
            file_key=file_key,
            file_name=file_name,
            file_size=len(file_data),
            mime_type=mime_type,
            admin_id=admin.id,
            expires_at=expires_at,
            notes=notes,
        )
        return StandardResponse(data=doc, message="Document replaced")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
            service_type=body.service_type,
            technician_notes=body.technician_notes,
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
