from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.payment_service_client import PaymentServiceClient
from app.config import settings
from app.dependencies import get_db, get_publisher, get_s3_client
from app.repositories.fleet_repo import FleetRepository
from app.repositories.driver_repo import DriverRepository
from app.repositories.fleet_company_repo import FleetCompanyRepository
from app.repositories.fleet_document_repo import FleetDocumentRepository
from app.schemas.fleet_application import FleetDocumentResponse
from app.schemas.fleet_company import (
    AddFleetPartnerRequest,
    FleetCompanyDetailResponse,
    FleetCompanyKPIs,
    FleetCompanyResponse,
    ToggleStatusRequest,
    UpdateFleetProfileRequest,
)
from app.schemas.fleet import FleetResponse
from app.schemas.driver import FleetDriverResponse
from app.services.fleet_company_service import FleetCompanyService
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
) -> FleetCompanyService:
    return FleetCompanyService(
        fleet_company_repo=FleetCompanyRepository(session),
        fleet_repo=FleetRepository(session),
        driver_repo=DriverRepository(session),
        doc_repo=FleetDocumentRepository(session),
        payment_client=PaymentServiceClient(settings.PAYMENT_SERVICE_URL),
        publisher=publisher,
    )


# --- Static routes first ---


@router.get(
    "/admin/fleet/companies/kpis",
    response_model=StandardResponse[FleetCompanyKPIs],
)
async def get_fleet_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetCompanyService = Depends(_get_service),
):
    kpis = await service.get_fleet_kpis()
    return StandardResponse(data=kpis)


@router.get(
    "/admin/fleet/companies",
    response_model=PaginatedResponse[FleetCompanyResponse],
)
async def list_fleets(
    status: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetCompanyService = Depends(_get_service),
):
    offset = (page - 1) * limit
    fleets, total = await service.list_fleets(
        status_filter=status, search=search, offset=offset, limit=limit
    )
    return PaginatedResponse(
        data=fleets,
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.post(
    "/admin/fleet/companies",
    response_model=StandardResponse[FleetResponse],
    status_code=201,
)
async def add_fleet_partner(
    body: AddFleetPartnerRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetCompanyService = Depends(_get_service),
):
    fleet = await service.add_fleet_partner(
        admin_id=user.id,
        **body.model_dump(),
    )
    return StandardResponse(
        data=FleetResponse.model_validate(fleet),
        message="Fleet partner added",
    )


# --- Dynamic routes ---


@router.get(
    "/admin/fleet/companies/{business_id}",
    response_model=StandardResponse[FleetCompanyDetailResponse],
)
async def get_fleet_detail(
    business_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetCompanyService = Depends(_get_service),
):
    detail = await service.get_fleet_detail(business_id)
    return StandardResponse(data=detail)


@router.put(
    "/admin/fleet/companies/{business_id}",
    response_model=StandardResponse[FleetResponse],
)
async def update_fleet_profile(
    business_id: UUID,
    body: UpdateFleetProfileRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetCompanyService = Depends(_get_service),
):
    fleet = await service.update_fleet_profile(
        fleet_id=business_id,
        **body.model_dump(exclude_unset=True),
    )
    return StandardResponse(
        data=FleetResponse.model_validate(fleet),
        message="Fleet profile updated",
    )


@router.put(
    "/admin/fleet/companies/{business_id}/status",
    response_model=StandardResponse[FleetResponse],
)
async def toggle_fleet_status(
    business_id: UUID,
    body: ToggleStatusRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetCompanyService = Depends(_get_service),
):
    fleet = await service.toggle_fleet_status(
        fleet_id=business_id,
        is_active=body.is_active,
        admin_id=user.id,
    )
    return StandardResponse(
        data=FleetResponse.model_validate(fleet),
        message=f"Fleet status updated to {'active' if body.is_active else 'suspended'}",
    )


@router.get(
    "/admin/fleet/companies/{business_id}/documents",
    response_model=StandardResponse[list[FleetDocumentResponse]],
)
async def list_fleet_documents(
    business_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    doc_repo = FleetDocumentRepository(session)
    docs = await doc_repo.list_by_fleet(business_id)
    return StandardResponse(
        data=[FleetDocumentResponse.model_validate(d) for d in docs],
    )


@router.post(
    "/admin/fleet/companies/{business_id}/documents",
    response_model=StandardResponse[FleetDocumentResponse],
    status_code=201,
)
async def upload_fleet_document(
    business_id: UUID,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetCompanyService = Depends(_get_service),
    s3_client: S3StorageClient = Depends(get_s3_client),
):
    file_data = await file.read()
    file_key = f"fleet-documents/{business_id}/{document_type}/{file.filename or 'document'}"

    await s3_client.upload_file(
        bucket=settings.S3_BUCKET_DOCUMENTS,
        key=file_key,
        data=file_data,
        content_type=file.content_type or "application/octet-stream",
    )

    doc = await service.upload_document(
        fleet_id=business_id,
        document_type=document_type,
        file_key=file_key,
        file_name=file.filename or "document",
        file_size=len(file_data),
        mime_type=file.content_type or "application/octet-stream",
    )

    return StandardResponse(
        data=FleetDocumentResponse.model_validate(doc),
        message="Document uploaded",
    )


@router.get(
    "/admin/fleet/companies/{business_id}/drivers",
    response_model=PaginatedResponse[FleetDriverResponse],
)
async def list_fleet_drivers(
    business_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * limit
    driver_repo = DriverRepository(session)
    drivers, total = await driver_repo.list_by_fleet(
        fleet_id=business_id, offset=offset, limit=limit
    )
    data = []
    for d in drivers:
        u = d.user
        f = d.fleet
        data.append(FleetDriverResponse(
            user_id=d.user_id,
            business_id=d.business_id,
            first_name=u.first_name if u else "",
            last_name=u.last_name if u else "",
            email=u.email if u else None,
            phone=u.phone if u else None,
            avatar_url=u.avatar_url if u else None,
            fleet_name=f.name if f else None,
            license_number=d.license_number,
            license_expiry=d.license_expiry,
            vehicle_type=d.vehicle_type,
            vehicle_make=d.vehicle_make,
            vehicle_model=d.vehicle_model,
            vehicle_year=d.vehicle_year,
            vehicle_plate=d.vehicle_plate,
            vehicle_color=d.vehicle_color,
            vehicle_photo_url=d.vehicle_photo_url,
            background_check_status=d.background_check_status,
            account_status=d.account_status,
            is_approved=d.is_approved,
            is_online=d.is_online,
            rating=float(d.rating),
            total_trips=d.total_trips,
            specialty=d.specialty,
        ))
    return PaginatedResponse(
        data=data,
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )
