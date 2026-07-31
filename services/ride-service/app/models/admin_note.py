import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, false, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mediride_common.database.base import Base


class AdminNote(Base):
    __tablename__ = "admin_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ride_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("rides.id"), nullable=False, index=True
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    author_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="admin"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Admin notes are internal by default; flagging one surfaces it to the
    # assigned driver on the ride detail they already fetch.
    is_driver_visible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false(), default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    ride = relationship("Ride", backref="admin_notes")
