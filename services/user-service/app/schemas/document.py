from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class DocumentType(str, Enum):
    GOVERNMENT_ID_FRONT = "government_id_front"
    GOVERNMENT_ID_BACK = "government_id_back"
    DRIVERS_LICENSE_FRONT = "drivers_license_front"
    DRIVERS_LICENSE_BACK = "drivers_license_back"
    DRIVERS_LICENSE = "drivers_license"
    VEHICLE_INSURANCE = "vehicle_insurance"
    VEHICLE_REGISTRATION = "vehicle_registration"
    MEDICAL_TRANSPORT_CERTIFICATION = "medical_transport_certification"


ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "application/pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Identity documents a rider may upload for KYC. The vehicle and transport
# certification types are driver-only and are rejected for riders.
RIDER_DOCUMENT_TYPES = {
    DocumentType.GOVERNMENT_ID_FRONT,
    DocumentType.GOVERNMENT_ID_BACK,
    DocumentType.DRIVERS_LICENSE_FRONT,
    DocumentType.DRIVERS_LICENSE_BACK,
}


class DocumentUploadResponse(BaseModel):
    id: UUID
    document_type: str
    file_key: str
    file_name: str
    file_url: str | None = None
    verification_status: str
    created_at: datetime

    @model_validator(mode="after")
    def build_file_url(self) -> "DocumentUploadResponse":
        if self.file_key and not self.file_url:
            from app.config import settings

            self.file_url = f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET_DOCUMENTS}/{self.file_key}"
        return self


class DocumentResponse(BaseModel):
    id: UUID
    document_type: str
    file_key: str
    file_name: str
    file_size: int
    mime_type: str
    file_url: str | None = None
    verification_status: str
    rejection_reason: str | None = None
    presigned_url: str | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def build_file_url(self) -> "DocumentResponse":
        if self.file_key and not self.file_url:
            from app.config import settings

            self.file_url = f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET_DOCUMENTS}/{self.file_key}"
        return self


class DocumentVerifyRequest(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected)$")
    rejection_reason: str | None = Field(None, max_length=500)
