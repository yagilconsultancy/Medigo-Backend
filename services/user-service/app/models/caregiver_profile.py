import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mediride_common.database.base import Base


class CaregiverProfile(Base):
    __tablename__ = "caregiver_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    business_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("businesses.id"), nullable=True, index=True
    )

    # Caregiver-specific fields
    specialty: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # PSW, RPN, RN, HCA, Paramedic, OT, PT
    license_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    license_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Account management
    account_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )
    service_capabilities: Mapped[list | None] = mapped_column(
        JSONB, server_default="[]"
    )
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)

    # Suspension tracking
    suspension_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    suspended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    suspended_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Personal information
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    province: Mapped[str | None] = mapped_column(String(50), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Emergency contact
    emergency_contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Admin notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Stats (denormalized for performance, updated via events)
    rating: Mapped[float] = mapped_column(Numeric(3, 2), default=5.00)
    total_assignments: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("User", back_populates="caregiver_profile")
    fleet = relationship("Fleet", foreign_keys=[business_id])
