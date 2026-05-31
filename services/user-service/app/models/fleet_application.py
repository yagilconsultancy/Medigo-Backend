import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mediride_common.database.base import Base


class FleetApplication(Base):
    __tablename__ = "fleet_applications"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Company Information
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_registration_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    years_in_operation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    street_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    province: Mapped[str | None] = mapped_column(String(50), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Primary Contact Information
    contact_person: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    alternate_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Fleet Composition
    fleet_size: Mapped[int] = mapped_column(Integer, default=0)
    average_vehicle_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wheelchair_accessible_count: Mapped[int] = mapped_column(Integer, default=0)
    stretcher_accessible_count: Mapped[int] = mapped_column(Integer, default=0)
    ambulatory_vehicle_count: Mapped[int] = mapped_column(Integer, default=0)

    # Insurance & Compliance
    insurance_provider: Mapped[str | None] = mapped_column(String(255), nullable=True)
    policy_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    liability_coverage_amount: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Additional Information
    service_areas: Mapped[str | None] = mapped_column(Text, nullable=True)
    healthcare_contracts: Mapped[str | None] = mapped_column(Text, nullable=True)
    additional_info: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Consent
    consent_accuracy: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_compliance: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_contact: Mapped[bool] = mapped_column(Boolean, default=False)

    # Legacy field (kept for backwards compatibility)
    driver_count: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Application status
    status: Mapped[str] = mapped_column(String(30), default="pending")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    info_request_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("businesses.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    fleet = relationship("Fleet", backref="fleet_applications")
    documents = relationship("FleetDocument", back_populates="application", lazy="selectin")
