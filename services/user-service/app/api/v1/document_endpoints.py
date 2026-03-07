from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_publisher, get_s3_client
from app.config import settings
from app.repositories.document_repo import DocumentRepository
from app.schemas.document import (
    DocumentResponse,
    DocumentType,
    DocumentUploadResponse,
    DocumentVerifyRequest,
)
from app.services.document_service import DocumentService
from mediride_common.auth.dependencies import get_current_user, require_role
from mediride_common.auth.models import UserClaims
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse
from mediride_common.storage.s3_client import S3StorageClient

router = APIRouter()


def _get_document_service(
    session: AsyncSession = Depends(get_db),
    s3_client: S3StorageClient = Depends(get_s3_client),
    publisher: EventPublisher = Depends(get_publisher),
) -> DocumentService:
    return DocumentService(
        document_repo=DocumentRepository(session),
        s3_client=s3_client,
        bucket=settings.S3_BUCKET_DOCUMENTS,
        publisher=publisher,
    )


@router.post(
    "/me/documents",
    response_model=StandardResponse[DocumentUploadResponse],
)
async def upload_document(
    document_type: str = Form(...),
    file: UploadFile = File(...),
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: DocumentService = Depends(_get_document_service),
):
    """Upload a driver document (ID front/back, license, etc.)."""
    file_data = await file.read()
    document = await service.upload_document(
        user_id=user.id,
        document_type=document_type,
        file_data=file_data,
        file_name=file.filename or "unknown",
        content_type=file.content_type or "application/octet-stream",
        business_id=user.business_id,
    )
    return StandardResponse(
        data=DocumentUploadResponse(
            id=document.id,
            document_type=document.document_type,
            file_name=document.file_name,
            verification_status=document.verification_status,
            created_at=document.created_at,
        ),
        message="Document uploaded successfully",
    )


@router.get(
    "/me/documents",
    response_model=StandardResponse[list[DocumentUploadResponse]],
)
async def list_my_documents(
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: DocumentService = Depends(_get_document_service),
):
    """List all documents for the current driver."""
    documents = await service.list_documents(user.id)
    return StandardResponse(
        data=[
            DocumentUploadResponse(
                id=doc.id,
                document_type=doc.document_type,
                file_name=doc.file_name,
                verification_status=doc.verification_status,
                created_at=doc.created_at,
            )
            for doc in documents
        ],
        message="Documents retrieved",
    )


@router.get(
    "/me/documents/{document_id}",
    response_model=StandardResponse[DocumentResponse],
)
async def get_my_document(
    document_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: DocumentService = Depends(_get_document_service),
):
    """Get a specific document with a presigned download URL."""
    document, url = await service.get_document_with_url(
        document_id=document_id,
        requesting_user_id=user.id,
        requesting_role=user.role,
        requesting_business_id=user.business_id,
    )
    return StandardResponse(
        data=DocumentResponse(
            id=document.id,
            document_type=document.document_type,
            file_name=document.file_name,
            file_size=document.file_size,
            mime_type=document.mime_type,
            verification_status=document.verification_status,
            rejection_reason=document.rejection_reason,
            presigned_url=url,
            created_at=document.created_at,
            updated_at=document.updated_at,
        ),
        message="Document retrieved",
    )


@router.get(
    "/{user_id}/documents",
    response_model=StandardResponse[list[DocumentUploadResponse]],
)
async def list_user_documents(
    user_id: UUID,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN, UserRole.BUSINESS])),
    service: DocumentService = Depends(_get_document_service),
):
    """Admin/Business: List all documents for a user."""
    documents = await service.list_documents(user_id)
    return StandardResponse(
        data=[
            DocumentUploadResponse(
                id=doc.id,
                document_type=doc.document_type,
                file_name=doc.file_name,
                verification_status=doc.verification_status,
                created_at=doc.created_at,
            )
            for doc in documents
        ],
        message="Documents retrieved",
    )


@router.put(
    "/{user_id}/documents/{document_id}/verify",
    response_model=StandardResponse[DocumentResponse],
)
async def verify_document(
    user_id: UUID,
    document_id: UUID,
    request: DocumentVerifyRequest,
    admin: UserClaims = Depends(require_role([UserRole.ADMIN, UserRole.BUSINESS])),
    service: DocumentService = Depends(_get_document_service),
):
    """Admin/Business: Approve or reject a document."""
    document = await service.verify_document(
        document_id=document_id,
        admin_id=admin.id,
        status=request.status,
        rejection_reason=request.rejection_reason,
    )
    return StandardResponse(
        data=DocumentResponse(
            id=document.id,
            document_type=document.document_type,
            file_name=document.file_name,
            file_size=document.file_size,
            mime_type=document.mime_type,
            verification_status=document.verification_status,
            rejection_reason=document.rejection_reason,
            created_at=document.created_at,
            updated_at=document.updated_at,
        ),
        message=f"Document {request.status}",
    )
