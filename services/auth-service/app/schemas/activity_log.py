from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ActivityLogKPIs(BaseModel):
    total_logs: int = 0
    info: int = 0
    warnings: int = 0
    critical: int = 0


class ActivityLogItem(BaseModel):
    id: UUID
    action_title: str
    action_description: str
    category: str
    severity: str
    admin_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ActivityLogListResponse(BaseModel):
    items: list[ActivityLogItem]
    total: int
    page: int
    page_size: int


class CreateActivityLogRequest(BaseModel):
    admin_id: UUID
    admin_name: str
    admin_email: str
    action_title: str
    action_description: str
    category: str
    severity: str = "info"
    target_entity_id: str | None = None
    target_entity_type: str | None = None
