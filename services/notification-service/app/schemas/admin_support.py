from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# ── Support Center ──


class SupportKPIs(BaseModel):
    total_tickets: int = 0
    open: int = 0
    resolved: int = 0
    ride_disputes: int = 0


class SupportTicketItem(BaseModel):
    id: UUID
    ticket_id: str
    ticket_type: str | None
    subject: str
    rider_name: str | None = None
    driver_name: str | None = None
    priority: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SupportTicketListResponse(BaseModel):
    items: list[SupportTicketItem]
    total: int
    page: int
    page_size: int


class ResolveTicketRequest(BaseModel):
    response: str | None = None


# ── Contact Logs ──


class ContactLogKPIs(BaseModel):
    phone_calls: int = 0
    live_chats: int = 0
    emails_sent: int = 0


class ContactLogItem(BaseModel):
    id: UUID
    user_name: str
    user_role: str
    channel: str
    description: str
    agent_name: str
    duration_seconds: int | None = None
    outcome: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ContactLogListResponse(BaseModel):
    items: list[ContactLogItem]
    total: int
    page: int
    page_size: int


class CreateContactLogRequest(BaseModel):
    user_id: UUID
    user_name: str
    user_role: str
    channel: str
    description: str
    agent_name: str
    duration_seconds: int | None = None
    outcome: str
