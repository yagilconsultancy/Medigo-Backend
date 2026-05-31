from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db, get_publisher, get_s3_client
from app.repositories.fleet_application_repo import FleetApplicationRepository
from app.repositories.fleet_document_repo import FleetDocumentRepository
from app.repositories.fleet_repo import FleetRepository
from app.schemas.fleet_application import (
    FleetApplicationPublicCreate,
    FleetApplicationPublicResponse,
    FleetDocumentResponse,
)
from app.services.fleet_application_service import FleetApplicationService
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.responses import StandardResponse
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


@router.post(
    "/public/fleet/apply",
    response_model=StandardResponse[FleetApplicationPublicResponse],
    status_code=201,
)
async def submit_fleet_application(
    body: FleetApplicationPublicCreate,
    service: FleetApplicationService = Depends(_get_service),
):
    """Public endpoint for fleet partners to submit an application. No authentication required."""
    if not (body.consent_accuracy and body.consent_compliance and body.consent_contact):
        raise HTTPException(
            status_code=422,
            detail="All consent checkboxes must be accepted to submit an application.",
        )

    application = await service.create_public_application(**body.model_dump())

    return StandardResponse(
        data=FleetApplicationPublicResponse.model_validate(application),
        message="Fleet partner application submitted successfully",
    )


@router.post(
    "/public/fleet/apply/{app_id}/documents",
    response_model=StandardResponse[FleetDocumentResponse],
    status_code=201,
)
async def upload_fleet_application_document(
    app_id: UUID,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    service: FleetApplicationService = Depends(_get_service),
    s3_client: S3StorageClient = Depends(get_s3_client),
):
    """Public endpoint to upload documents for a fleet application. No authentication required."""
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
