from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class VehicleDocumentResponse(BaseModel):
    id: UUID
    vehicle_id: UUID
    document_type: str
    file_key: str
    file_name: str
    file_size: int
    mime_type: str
    expires_at: date | None = None
    status: str
    uploaded_by: UUID
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VehicleDocumentUploadResponse(BaseModel):
    id: UUID
    vehicle_id: UUID
    document_type: str
    file_name: str
    status: str
    expires_at: date | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


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
