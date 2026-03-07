from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class WithdrawalRequest(BaseModel):
    amount: float = Field(..., gt=0)
    payment_method_id: UUID


class WithdrawalFeeResponse(BaseModel):
    amount: float
    transaction_fee: float
    net_amount: float


class WithdrawalResponse(BaseModel):
    id: UUID
    driver_id: UUID
    amount: float
    transaction_fee: float
    net_amount: float
    payment_method_id: UUID
    status: str
    processed_at: datetime | None = None
    failure_reason: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
