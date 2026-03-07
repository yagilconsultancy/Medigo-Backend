from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AddPaymentMethodRequest(BaseModel):
    method_type: str = Field(..., description="e.g. 'credit_card', 'debit_card'")
    card_number: str = Field(..., min_length=13, max_length=19)
    expiry_month: str = Field(..., min_length=1, max_length=2, pattern=r"^(0?[1-9]|1[0-2])$")
    expiry_year: str = Field(..., min_length=2, max_length=4, pattern=r"^\d{2,4}$")
    holder_name: str = Field(..., min_length=1, max_length=200)
    cvd: str | None = Field(None, min_length=3, max_length=4)


class PaymentMethodResponse(BaseModel):
    id: UUID
    user_id: UUID
    method_type: str
    last_four: str
    brand: str | None = None
    holder_name: str
    is_default: bool
    created_at: datetime

    model_config = {"from_attributes": True}
