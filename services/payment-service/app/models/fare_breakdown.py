import uuid
from datetime import datetime
from sqlalchemy import DateTime, Numeric, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from mediride_common.database.base import Base

class FareBreakdown(Base):
    __tablename__ = "fare_breakdowns"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ride_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, unique=True, index=True)
    base_fare: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    distance_charge: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    medical_assist_premium: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    service_fee: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    platform_fee: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    tips: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    incentives_bonuses: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    total_fare: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    driver_earnings: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
