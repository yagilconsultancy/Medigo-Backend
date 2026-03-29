import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mediride_common.database.base import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False, index=True
    )
    driver_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("driver_profiles.user_id"), nullable=True, index=True
    )
    vehicle_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    make: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    plate_number: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vin: Mapped[str | None] = mapped_column(String(17), nullable=True, unique=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mileage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    insurance_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    registration_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    passenger_capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    special_equipment: Mapped[list | None] = mapped_column(JSON, nullable=True)
    insurance_provider: Mapped[str | None] = mapped_column(String(255), nullable=True)
    registration_authority: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_inspection_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    fleet = relationship("Fleet", backref="vehicles")
    driver_profile = relationship("DriverProfile", backref="assigned_vehicle")
    maintenance_logs = relationship(
        "VehicleMaintenanceLog", back_populates="vehicle", lazy="selectin"
    )
    documents = relationship(
        "VehicleDocument", back_populates="vehicle", lazy="selectin"
    )
