import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from mediride_common.database.base import Base


class TrackingSession(Base):
    __tablename__ = "tracking_sessions"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ride_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    driver_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    rider_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)

    # Current driver position
    current_latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    current_longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    current_heading: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)
    current_speed: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)

    # ETA and distance
    eta_minutes: Mapped[float | None] = mapped_column(Numeric(6, 1), nullable=True)
    distance_remaining_miles: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)

    # Route endpoints
    pickup_latitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    pickup_longitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    destination_latitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    destination_longitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_tracking_sessions_ride_status", "ride_id", "status"),
    )
