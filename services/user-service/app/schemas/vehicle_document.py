from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, model_validator


class VehicleDocumentResponse(BaseModel):
    id: UUID
    vehicle_id: UUID
    document_type: str
    file_key: str
    file_name: str
    file_size: int
    mime_type: str
    file_url: str | None = None
    expires_at: date | None = None
    status: str
    uploaded_by: UUID
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def build_file_url(self) -> "VehicleDocumentResponse":
        if self.file_key and not self.file_url:
            from app.config import settings

            self.file_url = f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET_DOCUMENTS}/{self.file_key}"
        return self


class VehicleDocumentUploadResponse(BaseModel):
    id: UUID
    vehicle_id: UUID
    document_type: str
    file_key: str
    file_name: str
    file_url: str | None = None
    status: str
    expires_at: date | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def build_file_url(self) -> "VehicleDocumentUploadResponse":
        if self.file_key and not self.file_url:
            from app.config import settings

            self.file_url = f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET_DOCUMENTS}/{self.file_key}"
        return self


class VehicleDocumentKPIs(BaseModel):
    total_documents: int
    valid_count: int
    expiring_soon_count: int
    expired_count: int


class VehicleDocumentMatrixItem(BaseModel):
    document_type: str
    status: str
    file_name: str | None = None
    expires_at: date | None = None
    doc_id: UUID | None = None


class VehicleDocumentOverviewItem(BaseModel):
    vehicle_id: UUID
    vehicle_name: str | None = None
    make: str
    model: str
    plate_number: str
    fleet_name: str | None = None
    documents: list[VehicleDocumentMatrixItem]


class VehicleDocumentOverview(BaseModel):
    kpis: VehicleDocumentKPIs
    vehicles: list[VehicleDocumentOverviewItem]
    total: int
    page: int
    limit: int
    total_pages: int
