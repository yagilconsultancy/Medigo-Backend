from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DisciplinaryKPIs(BaseModel):
    total: int = 0
    suspensions: int = 0
    warnings: int = 0
    reinstated: int = 0


class DisciplinaryActionResponse(BaseModel):
    id: UUID
    action_number: int
    incident_id: UUID | None = None
    incident_number: int | None = None
    investigation_id: UUID | None = None
    action_type: str
    severity: str
    status: str
    subject_name: str
    subject_id: UUID
    subject_type: str
    issued_by_name: str
    issued_by_id: UUID
    duration_text: str
    duration_days: int | None = None
    issued_at: datetime
    expires_at: datetime | None = None
    reinstated_at: datetime | None = None
    reason: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DisciplinaryListResponse(BaseModel):
    items: list[DisciplinaryActionResponse]
    total: int
    page: int
    page_size: int


class CreateDisciplinaryActionRequest(BaseModel):
    incident_id: UUID | None = None
    incident_number: int | None = None
    investigation_id: UUID | None = None
    action_type: str
    severity: str
    subject_name: str
    subject_id: UUID
    subject_type: str
    duration_text: str
    duration_days: int | None = None
    expires_at: datetime | None = None
    reason: str | None = None


class DisciplinaryReasonResponse(BaseModel):
    reason: str | None = None
