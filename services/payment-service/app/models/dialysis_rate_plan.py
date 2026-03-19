import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from mediride_common.database.base import Base


class DialysisRatePlan(Base):
    __tablename__ = "dialysis_rate_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plan_name: Mapped[str] = mapped_column(String(200), nullable=False)
    origin_area: Mapped[str] = mapped_column(String(100), nullable=False)
    destination_area: Mapped[str] = mapped_column(String(100), nullable=False)
    per_trip_rate: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    monthly_package_rate: Mapped[float | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    monthly_package_trips: Mapped[int] = mapped_column(Integer, default=12)
    min_trips_per_week: Mapped[int] = mapped_column(Integer, default=3)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
