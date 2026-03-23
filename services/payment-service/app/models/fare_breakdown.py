import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
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

    # Rate card system columns
    distance_km: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    wait_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    wait_time_charge: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True, default=0)
    surcharges_total: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True, default=0)
    surcharges_capped: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True, default=0)
    surcharge_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    highway_407_toll: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True, default=0)
    insurance_gateway_fee: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True, default=0)
    flat_surcharge: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True, default=0)
    is_dialysis_rate: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    dialysis_plan_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    rate_card_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Fleet tracking columns
    business_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    driver_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)

    # Denormalized for admin dashboard analytics (avoids cross-DB joins)
    ride_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    pickup_city: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
