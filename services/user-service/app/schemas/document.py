from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    GOVERNMENT_ID_FRONT = "government_id_front"
    GOVERNMENT_ID_BACK = "government_id_back"
    DRIVERS_LICENSE_FRONT = "drivers_license_front"
    DRIVERS_LICENSE_BACK = "drivers_license_back"
    VEHICLE_INSURANCE = "vehicle_insurance"
    VEHICLE_REGISTRATION = "vehicle_registration"


ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "application/pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


class DocumentUploadResponse(BaseModel):
    id: UUID
    document_type: str
    file_name: str
    verification_status: str
    created_at: datetime


class DocumentResponse(BaseModel):
    id: UUID
    document_type: str
    file_name: str
    file_size: int
    mime_type: str
    verification_status: str
    rejection_reason: str | None = None
    presigned_url: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentVerifyRequest(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected)$")
    rejection_reason: str | None = Field(None, max_length=500)
