import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mediride_common.database.base import Base


class DisciplinaryAction(Base):
    __tablename__ = "disciplinary_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    action_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("incidents.id"), nullable=True
    )
    incident_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    investigation_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("investigations.id"), nullable=True
    )
    action_type: Mapped[str] = mapped_column(String(30), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="issued")
    subject_name: Mapped[str] = mapped_column(String(200), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(10), nullable=False)
    issued_by_name: Mapped[str] = mapped_column(String(200), nullable=False)
    issued_by_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    duration_text: Mapped[str] = mapped_column(String(50), nullable=False)
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reinstated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    incident = relationship("Incident", lazy="selectin")
    investigation = relationship("Investigation", lazy="selectin")
