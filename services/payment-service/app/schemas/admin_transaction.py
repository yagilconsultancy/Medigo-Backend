from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TransactionKPIsResponse(BaseModel):
    total_transactions: int
    total_collected: float
    refund_count: int
    pending_count: int


class PaymentMethodBreakdownItem(BaseModel):
    method_type: str
    display_name: str
    amount: float
    count: int


class AdminTransactionResponse(BaseModel):
    id: UUID
    ride_id: UUID | None = None
    rider_name: str = "Unknown"
    driver_name: str | None = None
    ride_type: str | None = None
    amount: float
    payment_method: str | None = None
    status: str
    transaction_type: str
    created_at: datetime

    model_config = {"from_attributes": True}
