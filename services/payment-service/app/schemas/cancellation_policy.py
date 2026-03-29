import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CancellationKPIs(BaseModel):
    service_type_count: int = 0
    fee_tier_count: int = 0
    max_fee: Decimal = Decimal("0")
    free_cancellation_window: str = "24+ hours"


class CancellationPolicyItem(BaseModel):
    id: uuid.UUID
    service_type: str
    cancellation_window: str
    fee: Decimal
    who_receives: str
    notes: str | None = None
    sort_order: int
    is_active: bool


class ServiceTypeBreakdown(BaseModel):
    service_type: str
    policies: list[CancellationPolicyItem]


class CancellationPolicyResponse(BaseModel):
    matrix: list[CancellationPolicyItem]
    by_service_type: list[ServiceTypeBreakdown]


class CancellationPolicyUpdateItem(BaseModel):
    id: uuid.UUID
    fee: Decimal | None = None
    who_receives: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class CancellationPolicyBulkUpdate(BaseModel):
    updates: list[CancellationPolicyUpdateItem]
