import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mediride_common.database.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    last_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    home_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    medical_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    business_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("businesses.id"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Insurance (rider)
    insurance_provider: Mapped[str | None] = mapped_column(String(255), nullable=True)
    insurance_policy_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Suspension (rider)
    suspended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    suspension_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    suspended_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )

    # Consent fields
    consent_emergency_services: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_privacy_policy: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_terms_of_service: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_data_location: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Onboarding tracking
    onboarding_step: Mapped[int] = mapped_column(Integer, default=1)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)

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
    driver_profile = relationship(
        "DriverProfile", back_populates="user", uselist=False, lazy="selectin"
    )
    caregiver_profile = relationship(
        "CaregiverProfile", back_populates="user", uselist=False, lazy="selectin"
    )
    emergency_contacts = relationship(
        "EmergencyContact", back_populates="user", lazy="selectin"
    )
    passengers = relationship("Passenger", back_populates="user", lazy="selectin")
