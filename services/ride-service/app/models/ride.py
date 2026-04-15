import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mediride_common.database.base import Base
from mediride_common.schemas.enums import (
    RideStatus,
    RideType,
    TripStructure,
    TripType,
)


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
    caregiver_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    business_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )

    # Business assignment (2-level dispatch)
    assigned_to_business_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    assigned_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    assigned_to_business_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    business_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    business_assignment_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Ride classification
    ride_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RideType.AMBULATORY
    )
    trip_type: Mapped[str] = mapped_column(
        String(30), default=TripType.TRANSPORT_ONLY
    )
    trip_structure: Mapped[str] = mapped_column(
        String(20), default=TripStructure.ONE_WAY
    )

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
    status: Mapped[str] = mapped_column(
        String(40), default=RideStatus.REQUESTED, index=True
    )

    # Medical info
    visit_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
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

    # Highway 407 toll
    use_highway_407: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    highway_407_route: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    # Dialysis trip flag
    is_dialysis_trip: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    # Booking source
    booking_channel: Mapped[str] = mapped_column(
        String(30), default="mobile_app", server_default="mobile_app"
    )
    facility_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
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
