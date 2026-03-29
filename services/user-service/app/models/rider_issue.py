import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Sequence, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mediride_common.database.base import Base

rider_issue_ticket_seq = Sequence("rider_issue_ticket_seq", start=8800)


class RiderIssue(Base):
    __tablename__ = "rider_issues"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticket_number: Mapped[int] = mapped_column(
        Integer, rider_issue_ticket_seq, server_default=rider_issue_ticket_seq.next_value(), nullable=False
    )
    rider_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    issue_type: Mapped[str] = mapped_column(String(50), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open")
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    notes = relationship(
        "RiderIssueNote",
        back_populates="issue",
        lazy="selectin",
        order_by="desc(RiderIssueNote.created_at)",
    )
    rider = relationship("User", lazy="selectin")
