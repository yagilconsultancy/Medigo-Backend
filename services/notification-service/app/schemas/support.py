from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateTicketRequest(BaseModel):
    subject: str = Field(..., max_length=255)
    category: str
    description: str = Field(..., min_length=10, max_length=5000)
    priority: str = "medium"


class SupportTicketResponse(BaseModel):
    id: UUID
    user_id: UUID
    subject: str
    category: str
    description: str
    status: str
    priority: str
    response: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class HelpArticleResponse(BaseModel):
    id: UUID
    title: str
    slug: str
    category: str
    content: str
    is_popular: bool
    view_count: int

    model_config = {"from_attributes": True}


class HelpArticleSummary(BaseModel):
    id: UUID
    title: str
    slug: str
    category: str
    is_popular: bool

    model_config = {"from_attributes": True}
