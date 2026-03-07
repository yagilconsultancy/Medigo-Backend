import uuid
from datetime import date, datetime
from sqlalchemy import Date, DateTime, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from mediride_common.database.base import Base

class EarningsPeriod(Base):
    __tablename__ = "earnings_periods"
    __table_args__ = (UniqueConstraint("driver_id", "period_type", "period_start", name="uq_driver_period"),)
    
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    driver_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    period_type: Mapped[str] = mapped_column(String(10), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    total_earnings: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    trip_count: Mapped[int] = mapped_column(Integer, default=0)
    hours_online: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    base_fares: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    distance_charges: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    medical_premiums: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    tips: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    incentives: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    platform_fees: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    net_earnings: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
