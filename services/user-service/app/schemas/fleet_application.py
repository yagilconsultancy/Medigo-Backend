from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FleetApplicationCreate(BaseModel):
    company_name: str = Field(..., max_length=255)
    contact_person: str = Field(..., max_length=255)
    email: str = Field(..., max_length=255)
    phone: str | None = Field(None, max_length=20)
    city: str | None = Field(None, max_length=100)
    province: str | None = Field(None, max_length=50)
    fleet_size: int = Field(0, ge=0)
    driver_count: int = Field(0, ge=0)
    description: str | None = None


class ApproveApplicationRequest(BaseModel):
    notes: str | None = None


class RejectApplicationRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class RequestInfoRequest(BaseModel):
    message: str = Field(..., min_length=1)


class FleetDocumentResponse(BaseModel):
    id: UUID
    document_type: str
    file_name: str
    file_size: int
    mime_type: str
    verification_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FleetApplicationResponse(BaseModel):
    id: UUID
    company_name: str
    contact_person: str
    email: str
    phone: str | None = None
    city: str | None = None
    province: str | None = None
    fleet_size: int
    driver_count: int
    description: str | None = None
    status: str
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None
    info_request_message: str | None = None
    business_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    documents: list[FleetDocumentResponse] = []

    model_config = {"from_attributes": True}


class FleetApplicationKPIs(BaseModel):
    total_applications: int
    pending_review: int
    approved: int
    rejected: int
