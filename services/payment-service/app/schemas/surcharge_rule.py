import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class SurchargeKPIs(BaseModel):
    active_count: int = 0
    inactive_count: int = 0
    total_count: int = 0


class SurchargeRuleResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    surcharge_type: str
    multiplier: Decimal
    flat_amount: Decimal
    schedule: dict[str, Any] | None = None
    applies_to: list[str] | None = None
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class SurchargeRuleListResponse(BaseModel):
    rules: list[SurchargeRuleResponse]


class SurchargeRuleCreate(BaseModel):
    name: str
    description: str | None = None
    surcharge_type: str
    multiplier: Decimal = Decimal("1.0")
    flat_amount: Decimal = Decimal("0")
    schedule: dict[str, Any] | None = None
    applies_to: list[str] | None = None
    is_active: bool = True
    sort_order: int = 0


class SurchargeRuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    surcharge_type: str | None = None
    multiplier: Decimal | None = None
    flat_amount: Decimal | None = None
    schedule: dict[str, Any] | None = None
    applies_to: list[str] | None = None
    is_active: bool | None = None
    sort_order: int | None = None
