from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.auth_service_client import AuthServiceClient
from app.clients.ride_service_client import RideServiceClient
from app.config import settings
from app.dependencies import get_db, get_publisher, get_s3_client
from app.repositories.admin_driver_repo import AdminDriverRepository
from app.repositories.document_repo import DocumentRepository
from app.repositories.fleet_repo import FleetRepository
from app.repositories.invitation_repo import InvitationRepository
from app.repositories.vehicle_repo import VehicleRepository
from app.schemas.admin_driver import (
    AdminDriverDetailResponse,
    AdminDriverDocumentOverview,
    AdminDriverListResponse,
    AdminDriverStatusOverview,
    CreateDriverRequest,
    ReassignFleetRequest,
    SuspendDriverRequest,
    UpdateDriverRequest,
)
from app.services.admin_driver_service import AdminDriverService
from app.services.document_service import DocumentService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse
from mediride_common.storage.s3_client import S3StorageClient

router = APIRouter(prefix="/admin/drivers")


def _get_service(
    session: AsyncSession = Depends(get_db),
    publisher: EventPublisher = Depends(get_publisher),
    s3_client: S3StorageClient = Depends(get_s3_client),
) -> AdminDriverService:
    document_service = DocumentService(
        document_repo=DocumentRepository(session),
        s3_client=s3_client,
        bucket=settings.S3_BUCKET_DOCUMENTS,
        publisher=publisher,
    )
    return AdminDriverService(
        repo=AdminDriverRepository(session),
        publisher=publisher,
        auth_client=AuthServiceClient(settings.AUTH_SERVICE_URL),
        ride_client=RideServiceClient(settings.RIDE_SERVICE_URL),
        invitation_repo=InvitationRepository(session),
        fleet_repo=FleetRepository(session),
        vehicle_repo=VehicleRepository(session),
        document_service=document_service,
    )


# --- Static routes first (before /{driver_id}) ---


@router.get("/documents/overview", response_model=StandardResponse[AdminDriverDocumentOverview])
async def get_document_overview(
    search: str | None = None,
    status_filter: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDriverService = Depends(_get_service),
):
    """Driver documents overview with KPIs and per-driver document matrix."""
    result = await service.get_document_overview(
        search=search, status_filter=status_filter, page=page, limit=limit
    )
    return StandardResponse(data=result)


@router.get("/status/overview", response_model=StandardResponse[AdminDriverStatusOverview])
async def get_status_overview(
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDriverService = Depends(_get_service),
):
    """Driver status overview with KPIs and drivers grouped by status."""
    result = await service.get_driver_status_overview()
    return StandardResponse(data=result)


# --- List + Create ---


@router.get("", response_model=StandardResponse[AdminDriverListResponse])
async def list_drivers(
    search: str | None = None,
    fleet_id: UUID | None = None,
    account_status: str | None = None,
    is_online: bool | None = None,
    sort_by: str = Query("created_at", pattern="^(created_at|name|rating|total_trips)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDriverService = Depends(_get_service),
):
    """List all drivers with KPIs, search, filters, and pagination."""
    result = await service.list_drivers(
        search=search,
        fleet_id=fleet_id,
        account_status=account_status,
        is_online=is_online,
        sort_by=sort_by,
        page=page,
        limit=limit,
    )
    return StandardResponse(data=result)


@router.post("", response_model=StandardResponse[AdminDriverDetailResponse])
async def create_driver(
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    fleet_id: UUID = Form(...),
    phone: str | None = Form(None),
    license_number: str | None = Form(None),
    license_expiry: date | None = Form(None),
    medical_transport_certification: str | None = Form(None),
    background_check_status: str = Form("approved"),
    vehicle_id: UUID | None = Form(None),
    service_capabilities: str | None = Form(
        None,
        description="Comma-separated list of capabilities (e.g. 'wheelchair,stretcher')",
    ),
    specialty: str | None = Form(None),
    date_of_birth: date | None = Form(None),
    account_status: str = Form("active"),
    is_approved: bool = Form(False, description="Approve driver immediately (default: False)"),
    vehicle_insurance_file: UploadFile | None = File(None),
    drivers_license_file: UploadFile | None = File(None),
    certificate_file: UploadFile | None = File(None),
    admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDriverService = Depends(_get_service),
):
    """
    Create a new driver (credentials + user + profile) with optional document uploads.

    Accepts `multipart/form-data` so admins can attach:
      - `vehicle_insurance_file`: Vehicle insurance document
      - `drivers_license_file`: Driver's license
      - `certificate_file`: Medical transport certification
    """
    capabilities_list: list[str] = []
    if service_capabilities:
        capabilities_list = [c.strip() for c in service_capabilities.split(",") if c.strip()]

    request = CreateDriverRequest(
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        fleet_id=fleet_id,
        license_number=license_number,
        license_expiry=license_expiry,
        medical_transport_certification=medical_transport_certification,
        background_check_status=background_check_status,
        vehicle_id=vehicle_id,
        service_capabilities=capabilities_list,
        specialty=specialty,
        date_of_birth=date_of_birth,
        account_status=account_status,
        is_approved=is_approved,
    )

    documents: dict[str, UploadFile] = {}
    if vehicle_insurance_file is not None:
        documents["vehicle_insurance"] = vehicle_insurance_file
    if drivers_license_file is not None:
        documents["drivers_license"] = drivers_license_file
    if certificate_file is not None:
        documents["medical_transport_certification"] = certificate_file

    result = await service.create_driver(admin.id, request, documents=documents)
    return StandardResponse(data=result, message="Driver created successfully")


# --- Single driver routes ---


@router.get("/{driver_id}", response_model=StandardResponse[AdminDriverDetailResponse])
async def get_driver_detail(
    driver_id: UUID,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDriverService = Depends(_get_service),
):
    """Get full driver detail (profile, documents, trips, ratings)."""
    result = await service.get_driver_detail(driver_id)
    return StandardResponse(data=result)


@router.put("/{driver_id}", response_model=StandardResponse[AdminDriverDetailResponse])
async def update_driver(
    driver_id: UUID,
    request: UpdateDriverRequest,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDriverService = Depends(_get_service),
):
    """Update driver profile."""
    result = await service.update_driver(driver_id, request)
    return StandardResponse(data=result, message="Driver updated successfully")


@router.delete("/{driver_id}", response_model=StandardResponse[AdminDriverDetailResponse])
async def deactivate_driver(
    driver_id: UUID,
    admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDriverService = Depends(_get_service),
):
    """Deactivate a driver account."""
    result = await service.deactivate_driver(driver_id, admin.id)
    return StandardResponse(data=result, message="Driver deactivated")


# --- Actions ---


@router.put("/{driver_id}/approve", response_model=StandardResponse[AdminDriverDetailResponse])
async def approve_driver(
    driver_id: UUID,
    admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDriverService = Depends(_get_service),
):
    """Approve a pending driver."""
    result = await service.approve_driver(driver_id, admin.id)
    return StandardResponse(data=result, message="Driver approved")


@router.put("/{driver_id}/suspend", response_model=StandardResponse[AdminDriverDetailResponse])
async def suspend_driver(
    driver_id: UUID,
    request: SuspendDriverRequest,
    admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDriverService = Depends(_get_service),
):
    """Suspend a driver with a reason."""
    result = await service.suspend_driver(driver_id, request.reason, admin.id)
    return StandardResponse(data=result, message="Driver suspended")


@router.put("/{driver_id}/reactivate", response_model=StandardResponse[AdminDriverDetailResponse])
async def reactivate_driver(
    driver_id: UUID,
    admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDriverService = Depends(_get_service),
):
    """Reactivate a suspended or deactivated driver."""
    result = await service.reactivate_driver(driver_id, admin.id)
    return StandardResponse(data=result, message="Driver reactivated")


@router.post("/{driver_id}/resend-invite", response_model=StandardResponse)
async def resend_invitation(
    driver_id: UUID,
    admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDriverService = Depends(_get_service),
):
    """Resend invitation email to a driver. Returns the new invite token."""
    token = await service.resend_invitation(driver_id, admin.id)
    return StandardResponse(
        data={"invite_token": token},
        message="Invitation resent successfully",
    )


@router.post("/{driver_id}/resend-reactivation", response_model=StandardResponse)
async def resend_reactivation(
    driver_id: UUID,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDriverService = Depends(_get_service),
):
    """Resend the reactivation email to a driver still pending reactivation
    after an email change. Fails if the driver is already active."""
    email = await service.resend_reactivation(driver_id)
    return StandardResponse(
        data={"email": email},
        message="Reactivation email resent successfully",
    )


@router.put("/{driver_id}/reassign-fleet", response_model=StandardResponse[AdminDriverDetailResponse])
async def reassign_fleet(
    driver_id: UUID,
    request: ReassignFleetRequest,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDriverService = Depends(_get_service),
):
    """Reassign driver to a different fleet."""
    result = await service.reassign_fleet(driver_id, request.fleet_id)
    return StandardResponse(data=result, message="Driver fleet reassigned")


# --- Driver sub-resources ---


@router.get("/{driver_id}/documents", response_model=StandardResponse)
async def get_driver_documents(
    driver_id: UUID,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDriverService = Depends(_get_service),
):
    """Get a driver's documents."""
    docs = await service.repo.get_driver_documents(driver_id)
    return StandardResponse(data=docs)


@router.get("/{driver_id}/trips", response_model=StandardResponse)
async def get_driver_trips(
    driver_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDriverService = Depends(_get_service),
):
    """Get a driver's trip history from ride-service."""
    result = await service.ride_client.get_driver_completed_rides(
        driver_id, page=page, limit=limit
    )
    return StandardResponse(data=result or {"rides": [], "total": 0})


@router.get("/{driver_id}/ratings", response_model=StandardResponse)
async def get_driver_ratings(
    driver_id: UUID,
    limit: int = Query(10, ge=1, le=50),
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDriverService = Depends(_get_service),
):
    """Get a driver's ratings from ride-service."""
    result = await service.ride_client.get_driver_ratings(driver_id, limit=limit)
    return StandardResponse(data=result or {"ratings": [], "average_rating": 0, "total_ratings": 0})
