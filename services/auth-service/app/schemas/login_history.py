from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class LoginHistoryKPIs(BaseModel):
    total_logins: int = 0
    successful: int = 0
    failed_attempts: int = 0
    unique_locations: int = 0
    suspicious_count: int = 0


class LoginRecordItem(BaseModel):
    id: UUID
    admin_name: str
    admin_email: str
    ip_address: str
    device_info: str
    location: str | None = None
    success: bool
    failure_reason: str | None = None
    is_suspicious: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginHistoryListResponse(BaseModel):
    items: list[LoginRecordItem]
    total: int
    page: int
    page_size: int
