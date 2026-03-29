from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class InvestigationKPIs(BaseModel):
    active: int = 0
    assigned: int = 0
    unassigned: int = 0
    avg_duration_days: float = 0.0


class InvestigationNoteResponse(BaseModel):
    id: UUID
    investigation_id: UUID
    author_id: UUID
    author_name: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class InvestigationResponse(BaseModel):
    id: UUID
    investigation_number: int
    incident_id: UUID
    incident_number: int
    incident_type: str
    priority: str
    status: str
    subject_name: str
    assigned_to_id: UUID | None = None
    assigned_to_name: str | None = None
    progress_percent: int = 0
    opened_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    notes: list[InvestigationNoteResponse] = []

    model_config = {"from_attributes": True}


class InvestigationListResponse(BaseModel):
    items: list[InvestigationResponse]
    total: int
    page: int
    page_size: int


class AssignInvestigatorRequest(BaseModel):
    assigned_to_id: UUID
    assigned_to_name: str


class UpdateInvestigationStatusRequest(BaseModel):
    status: str


class UpdateProgressRequest(BaseModel):
    progress_percent: int


class CreateInvestigationNoteRequest(BaseModel):
    content: str
