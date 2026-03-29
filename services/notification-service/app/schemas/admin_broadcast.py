from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class BroadcastKPIs(BaseModel):
    total_sent: int = 0
    category_1_count: int = 0
    category_1_label: str = ""
    category_2_count: int = 0
    category_2_label: str = ""
    total_delivered: int = 0


class BroadcastResponse(BaseModel):
    id: UUID
    broadcast_type: str
    notification_type: str
    title: str
    message: str
    audience_segment: str
    sent_to_count: int
    delivered_count: int
    created_by_id: UUID
    sent_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class BroadcastListResponse(BaseModel):
    items: list[BroadcastResponse]
    total: int
    page: int
    page_size: int


class SendBroadcastRequest(BaseModel):
    notification_type: str
    title: str
    message: str
    audience_segment: str
    sent_to_count: int = 0
