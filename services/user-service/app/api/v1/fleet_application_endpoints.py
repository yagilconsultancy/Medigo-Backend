from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db, get_publisher, get_s3_client
from app.repositories.fleet_repo import FleetRepository
from app.repositories.fleet_application_repo import FleetApplicationRepository
from app.repositories.fleet_document_repo import FleetDocumentRepository
from app.schemas.fleet_application import (
    ApproveApplicationRequest,
    FleetApplicationCreate,
    FleetApplicationKPIs,
    FleetApplicationResponse,
    FleetDocumentResponse,
    RejectApplicationRequest,
    RequestInfoRequest,
)
from app.services.fleet_application_service import FleetApplicationService
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
) -> FleetApplicationService:
    return FleetApplicationService(
        app_repo=FleetApplicationRepository(session),
        doc_repo=FleetDocumentRepository(session),
        fleet_repo=FleetRepository(session),
        publisher=publisher,
    )


# --- Static routes first ---


@router.get(
    "/admin/fleet/applications/kpis",
    response_model=StandardResponse[FleetApplicationKPIs],
)
async def get_application_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetApplicationService = Depends(_get_service),
):
    kpis = await service.get_kpis()
    return StandardResponse(data=kpis)


@router.get(
    "/admin/fleet/applications",
    response_model=PaginatedResponse[FleetApplicationResponse],
)
async def list_applications(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetApplicationService = Depends(_get_service),
):
    offset = (page - 1) * limit
    applications, total = await service.list_applications(
        status_filter=status, offset=offset, limit=limit
    )
    return PaginatedResponse(
        data=[FleetApplicationResponse.model_validate(a) for a in applications],
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.post(
    "/admin/fleet/applications",
    response_model=StandardResponse[FleetApplicationResponse],
    status_code=201,
)
async def create_application(
    body: FleetApplicationCreate,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetApplicationService = Depends(_get_service),
):
    application = await service.create_application(
        admin_id=user.id,
        **body.model_dump(),
    )
    return StandardResponse(
        data=FleetApplicationResponse.model_validate(application),
        message="Fleet application created",
    )


# --- Dynamic routes ---


@router.get(
    "/admin/fleet/applications/{app_id}",
    response_model=StandardResponse[FleetApplicationResponse],
)
async def get_application(
    app_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetApplicationService = Depends(_get_service),
):
    application = await service.get_application(app_id)
    return StandardResponse(
        data=FleetApplicationResponse.model_validate(application),
    )


@router.put(
    "/admin/fleet/applications/{app_id}/approve",
    response_model=StandardResponse[FleetApplicationResponse],
)
async def approve_application(
    app_id: UUID,
    body: ApproveApplicationRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetApplicationService = Depends(_get_service),
):
    application = await service.approve_application(
        app_id=app_id,
        admin_id=user.id,
        notes=body.notes,
    )
    return StandardResponse(
        data=FleetApplicationResponse.model_validate(application),
        message="Application approved and fleet partner created",
    )


@router.put(
    "/admin/fleet/applications/{app_id}/reject",
    response_model=StandardResponse[FleetApplicationResponse],
)
async def reject_application(
    app_id: UUID,
    body: RejectApplicationRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetApplicationService = Depends(_get_service),
):
    application = await service.reject_application(
        app_id=app_id,
        admin_id=user.id,
        reason=body.reason,
    )
    return StandardResponse(
        data=FleetApplicationResponse.model_validate(application),
        message="Application rejected",
    )


@router.put(
    "/admin/fleet/applications/{app_id}/request-info",
    response_model=StandardResponse[FleetApplicationResponse],
)
async def request_info(
    app_id: UUID,
    body: RequestInfoRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetApplicationService = Depends(_get_service),
):
    application = await service.request_info(
        app_id=app_id,
        admin_id=user.id,
        message=body.message,
    )
    return StandardResponse(
        data=FleetApplicationResponse.model_validate(application),
        message="Additional information requested",
    )


@router.post(
    "/admin/fleet/applications/{app_id}/documents",
    response_model=StandardResponse[FleetDocumentResponse],
    status_code=201,
)
async def upload_application_document(
    app_id: UUID,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetApplicationService = Depends(_get_service),
    s3_client: S3StorageClient = Depends(get_s3_client),
):
    file_data = await file.read()
    file_key = f"fleet-applications/{app_id}/{document_type}/{file.filename or 'document'}"

    await s3_client.upload_file(
        bucket=settings.S3_BUCKET_DOCUMENTS,
        key=file_key,
        data=file_data,
        content_type=file.content_type or "application/octet-stream",
    )

    doc = await service.upload_document(
        app_id=app_id,
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
