import logging
import uuid as uuid_mod
from uuid import UUID

from app.models.driver_document import DriverDocument
from app.repositories.document_repo import DocumentRepository
from app.schemas.document import ALLOWED_MIME_TYPES, MAX_FILE_SIZE, DocumentType
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher
from mediride_common.events.schemas import DriverDocumentUploadedPayload
from mediride_common.exceptions import (
    AuthorizationError,
    NotFoundError,
    ValidationError,
)
from mediride_common.storage.s3_client import S3StorageClient

logger = logging.getLogger(__name__)

# Map MIME types to extensions
MIME_TO_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "application/pdf": "pdf",
}

# Magic bytes for file type validation
FILE_SIGNATURES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG": "image/png",
    b"%PDF": "application/pdf",
}


def _detect_mime_type(file_data: bytes) -> str | None:
    """Detect MIME type from file magic bytes."""
    for signature, mime_type in FILE_SIGNATURES.items():
        if file_data[: len(signature)] == signature:
            return mime_type
    return None


class DocumentService:
    def __init__(
        self,
        document_repo: DocumentRepository,
        s3_client: S3StorageClient,
        bucket: str,
        publisher: EventPublisher,
    ):
        self.document_repo = document_repo
        self.s3_client = s3_client
        self.bucket = bucket
        self.publisher = publisher

    async def upload_document(
        self,
        user_id: UUID,
        document_type: str,
        file_data: bytes,
        file_name: str,
        content_type: str,
        business_id: UUID | None = None,
    ) -> DriverDocument:
        """Upload a driver document."""
        # Validate document type
        try:
            DocumentType(document_type)
        except ValueError:
            valid_types = [t.value for t in DocumentType]
            raise ValidationError(
                f"Invalid document type. Must be one of: {', '.join(valid_types)}"
            )

        # Validate file size
        if len(file_data) > MAX_FILE_SIZE:
            raise ValidationError(
                f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)}MB"
            )

        if len(file_data) == 0:
            raise ValidationError("File is empty")

        # Validate MIME type from content-type header
        if content_type not in ALLOWED_MIME_TYPES:
            raise ValidationError(
                f"Invalid file type. Allowed: JPEG, PNG, PDF"
            )

        # Validate actual file content (magic bytes)
        detected_type = _detect_mime_type(file_data)
        if detected_type != content_type:
            raise ValidationError(
                "File content does not match the declared content type"
            )

        # Check if document of this type already exists (replace it)
        existing = await self.document_repo.get_by_user_and_type(
            user_id, document_type
        )
        if existing:
            await self.s3_client.delete_file(self.bucket, existing.file_key)
            await self.document_repo.delete(existing.id)

        # Generate unique S3 key
        ext = MIME_TO_EXT.get(content_type, "bin")
        file_key = f"documents/{user_id}/{document_type}/{uuid_mod.uuid4()}.{ext}"

        # Upload to S3
        await self.s3_client.upload_file(
            bucket=self.bucket,
            key=file_key,
            file_data=file_data,
            content_type=content_type,
        )

        # Create DB record
        document = DriverDocument(
            user_id=user_id,
            document_type=document_type,
            file_key=file_key,
            file_name=file_name,
            file_size=len(file_data),
            mime_type=content_type,
        )
        await self.document_repo.create(document)

        # Publish event
        if business_id:
            await self.publisher.publish(
                Exchanges.USERS,
                RoutingKeys.DRIVER_DOCUMENT_UPLOADED,
                DriverDocumentUploadedPayload(
                    user_id=user_id,
                    document_id=document.id,
                    document_type=document_type,
                    business_id=business_id,
                ).model_dump(mode="json"),
            )

        logger.info(
            f"Document uploaded: {document.id} type={document_type} user={user_id}"
        )
        return document

    async def get_document_with_url(
        self,
        document_id: UUID,
        requesting_user_id: UUID,
        requesting_role: str,
        requesting_business_id: UUID | None = None,
    ) -> tuple[DriverDocument, str]:
        """Get a document with a presigned URL."""
        document = await self.document_repo.get_by_id(document_id)
        if not document:
            raise NotFoundError("Document not found")

        # Authorization: owner, admin, or same-business manager
        if requesting_role not in ("admin", "business") and document.user_id != requesting_user_id:
            raise AuthorizationError("Not authorized to view this document")

        url = await self.s3_client.generate_presigned_url(
            bucket=self.bucket, key=document.file_key, expires_in=3600
        )
        return document, url

    async def list_documents(self, user_id: UUID) -> list[DriverDocument]:
        """List all documents for a user."""
        return await self.document_repo.list_by_user(user_id)

    async def verify_document(
        self,
        document_id: UUID,
        admin_id: UUID,
        status: str,
        rejection_reason: str | None = None,
    ) -> DriverDocument:
        """Admin: approve or reject a document."""
        document = await self.document_repo.get_by_id(document_id)
        if not document:
            raise NotFoundError("Document not found")

        if status == "rejected" and not rejection_reason:
            raise ValidationError("Rejection reason is required")

        await self.document_repo.update_status(
            document_id=document_id,
            status=status,
            verified_by=admin_id,
            rejection_reason=rejection_reason,
        )

        logger.info(
            f"Document {document_id} {status} by admin {admin_id}"
        )
        return await self.document_repo.get_by_id(document_id)
