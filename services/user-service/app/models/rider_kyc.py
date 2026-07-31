import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, false, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mediride_common.database.base import Base
from mediride_common.schemas.enums import KYCStatus


class RiderKYC(Base):
    """Identity verification record for a rider.

    One row per rider, keyed on the user id — a rider either has a KYC record
    or hasn't started one.
    """

    __tablename__ = "rider_kyc"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )

    # Identity document
    id_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    id_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    id_issuing_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    id_issuing_authority: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    id_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Verification workflow
    kyc_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=KYCStatus.NOT_STARTED, index=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set when an admin has checked the DOB against the identity document.
    dob_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false(), default=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", back_populates="kyc")
