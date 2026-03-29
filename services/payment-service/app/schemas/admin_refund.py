from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RefundKPIsResponse(BaseModel):
    total_requests: int
    pending_review: int
    approved: int
    rejected: int


class RefundRequestListItem(BaseModel):
    id: UUID
    ride_id: UUID
    rider_name: str = "Unknown"
    driver_name: str | None = None
    category: str
    reason: str | None = None
    amount: float
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RefundDetailResponse(BaseModel):
    id: UUID
    ride_id: UUID
    rider_id: UUID
    driver_id: UUID | None = None
    rider_name: str = "Unknown"
    rider_phone: str | None = None
    driver_name: str | None = None
    amount: float
    refund_amount: float | None = None
    is_partial: bool = False
    category: str
    reason: str | None = None
    status: str
    decision_note: str | None = None
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    ride_type: str | None = None
    payment_method_type: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateRefundRequest(BaseModel):
    ride_id: UUID
    rider_id: UUID
    driver_id: UUID | None = None
    amount: float = Field(..., gt=0)
    category: str
    reason: str | None = None
    ride_type: str | None = None
    payment_method_type: str | None = None


class ApproveRefundRequest(BaseModel):
    decision_note: str = Field(..., min_length=1, max_length=2000)
    is_partial: bool = False
    partial_amount: float | None = Field(default=None, gt=0)


class RejectRefundRequest(BaseModel):
    decision_note: str = Field(..., min_length=1, max_length=2000)
