import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mediride_common.database.base import Base


class Ride(Base):
    __tablename__ = "rides"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rider_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    driver_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    business_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )

    # Ride classification
    ride_type: Mapped[str] = mapped_column(String(20), nullable=False)
    trip_type: Mapped[str] = mapped_column(String(20), default="transport_only")
    trip_structure: Mapped[str] = mapped_column(String(20), default="one_way")

    # Locations
    pickup_address: Mapped[str] = mapped_column(Text, nullable=False)
    pickup_latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    pickup_longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    destination_address: Mapped[str] = mapped_column(Text, nullable=False)
    destination_latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    destination_longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)

    # Scheduling
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    pickup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dropoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(20), default="requested", index=True)

    # Medical info
    visit_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    appointment_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    facility_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    special_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Passenger info
    passenger_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    mobility_level: Mapped[str | None] = mapped_column(String(30), nullable=True)
    assistance_level: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Distance & duration
    estimated_distance_miles: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    actual_distance_miles: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    estimated_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Fare
    estimated_fare: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    final_fare: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Cancellation
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Sharing
    share_token: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)

    # Recurring ride reference
    recurring_ride_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    requests = relationship("RideRequest", back_populates="ride", lazy="selectin")
    ratings = relationship("RideRating", back_populates="ride", lazy="selectin")
    status_logs = relationship("RideStatusLog", back_populates="ride", lazy="selectin")
