from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SessionResponse(BaseModel):
    id: UUID
    device_name: str
    device_type: str
    ip_address: str | None = None
    last_active_at: datetime
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
