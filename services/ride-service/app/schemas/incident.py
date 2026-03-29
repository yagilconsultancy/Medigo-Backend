from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class IncidentKPIs(BaseModel):
    total: int = 0
    driver_complaints: int = 0
    rider_complaints: int = 0
    accidents: int = 0


class IncidentNoteResponse(BaseModel):
    id: UUID
    incident_id: UUID
    author_id: UUID
    author_name: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class IncidentResponse(BaseModel):
    id: UUID
    incident_number: int
    incident_type: str
    severity: str
    status: str
    subject_name: str
    subject_id: UUID | None = None
    subject_type: str
    filed_by_name: str
    filed_by_id: UUID | None = None
    filed_by_role: str
    ride_id: UUID | None = None
    description: str
    created_at: datetime
    updated_at: datetime
    notes: list[IncidentNoteResponse] = []

    model_config = {"from_attributes": True}


class IncidentListResponse(BaseModel):
    items: list[IncidentResponse]
    total: int
    page: int
    page_size: int


class CreateIncidentRequest(BaseModel):
    incident_type: str
    severity: str
    subject_name: str
    subject_id: UUID | None = None
    subject_type: str
    ride_id: UUID | None = None
    description: str


class UpdateIncidentStatusRequest(BaseModel):
    status: str


class CreateIncidentNoteRequest(BaseModel):
    content: str
