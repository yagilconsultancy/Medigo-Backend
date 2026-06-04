from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class ContactMessageRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    phone: str | None = Field(None, max_length=30)
    service_type: str = Field(..., min_length=1, max_length=50)
    message: str = Field(..., min_length=1)


class ContactMessageResponse(BaseModel):
    id: UUID
    full_name: str
    email: str
    phone: str | None = None
    service_type: str
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}
