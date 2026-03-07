from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: UUID
    title: str
    body: str
    notification_type: str
    data: dict | None = None
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UnreadCountResponse(BaseModel):
    unread_count: int
