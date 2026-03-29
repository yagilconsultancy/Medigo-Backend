import uuid
from datetime import datetime

from pydantic import BaseModel


class PricingLogItem(BaseModel):
    id: uuid.UUID
    log_number: int
    admin_id: uuid.UUID
    admin_name: str
    category: str
    city: str | None = None
    change_description: str
    before_value: str | None = None
    after_value: str | None = None
    created_at: datetime


class PricingLogListResponse(BaseModel):
    items: list[PricingLogItem]
    total: int
    page: int
    page_size: int


class PricingLogExportResponse(BaseModel):
    items: list[PricingLogItem]
    total: int
