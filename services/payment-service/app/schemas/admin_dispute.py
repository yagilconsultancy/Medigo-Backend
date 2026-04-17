from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── KPIs ──


class DisputeKPIsResponse(BaseModel):
    open_disputes: int
    refunds_approved: int
    rejected: int


# ── List ──


class DisputeListItem(BaseModel):
    id: UUID
    dispute_number: int
    dispute_type: str
    status: str
    rider_name: str
    trip_code: str
    billed_amount: float
    claimed_amount: float
    created_at: datetime

    model_config = {"from_attributes": True}


class DisputeListResponse(BaseModel):
    items: list[DisputeListItem]
    total: int
    page: int
    page_size: int


# ── Detail ──


class DisputeNoteItem(BaseModel):
    id: UUID
    admin_id: UUID
    admin_name: str
    note: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DisputeDetailResponse(BaseModel):
    id: UUID
    dispute_number: int
    dispute_type: str
    status: str
    ride_id: UUID
    rider_id: UUID
    rider_name: str
    driver_id: UUID | None
    driver_name: str | None
    trip_code: str
    billed_amount: float
    claimed_amount: float
    reason: str
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    decision_note: str | None
    refund_request_id: UUID | None
    created_at: datetime
    updated_at: datetime
    notes: list[DisputeNoteItem] = []

    model_config = {"from_attributes": True}


# ── Create ──


class CreateDisputeRequest(BaseModel):
    ride_id: UUID
    rider_id: UUID
    rider_name: str = Field(..., min_length=1, max_length=200)
    driver_id: UUID | None = None
    driver_name: str | None = Field(default=None, max_length=200)
    trip_code: str = Field(..., min_length=1, max_length=50)
    dispute_type: str
    billed_amount: float = Field(..., gt=0)
    claimed_amount: float = Field(..., ge=0)
    reason: str = Field(..., min_length=1, max_length=5000)


# ── Actions ──


class ApproveDisputeRequest(BaseModel):
    decision_note: str = Field(..., min_length=1, max_length=2000)
    create_refund: bool = False
    refund_amount: float | None = Field(default=None, gt=0)


class RejectDisputeRequest(BaseModel):
    decision_note: str = Field(..., min_length=1, max_length=2000)


# ── Notes ──


class CreateDisputeNoteRequest(BaseModel):
    note: str = Field(..., min_length=1, max_length=5000)
