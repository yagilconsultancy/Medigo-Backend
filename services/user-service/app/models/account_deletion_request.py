import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mediride_common.database.base import Base


class AccountDeletionRequest(Base):
    """A deletion request filed from the public web form at
    getmedigo.com/medigo-delete-account.

    Google Play requires a publicly reachable deletion URL that works without
    installing the app or logging in, so the requester is identified by the
    email on their MediGo account and proves ownership with an emailed OTP.
    An admin still reviews every verified request in the BackOffice before the
    account is actually deleted.
    """

    __tablename__ = "account_deletion_requests"

    # Lifecycle: pending_verification -> pending_review -> approved | rejected
    STATUS_PENDING_VERIFICATION = "pending_verification"
    STATUS_PENDING_REVIEW = "pending_review"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # What the requester typed on the public form.
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The account this request resolved to. Always set on creation: a request
    # row is only written when the email matches a live account, so admins
    # never review requests that cannot be actioned.
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=STATUS_PENDING_VERIFICATION, index=True
    )

    # Email ownership proof. The code itself is never stored - only an HMAC of
    # it - so a database leak does not hand out live deletion codes.
    otp_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    otp_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    otp_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    otp_sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    otp_last_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Admin review.
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Provenance, kept for the audit trail Play asks operators to maintain.
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, default="public_web", server_default="public_web"
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", foreign_keys=[user_id], lazy="selectin")
    reviewer = relationship("User", foreign_keys=[reviewed_by], lazy="selectin")
