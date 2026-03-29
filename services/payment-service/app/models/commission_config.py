import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from mediride_common.database.base import Base


class CommissionConfig(Base):
    __tablename__ = "commission_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    platform_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    driver_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    fleet_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    caregiver_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    reserve_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
