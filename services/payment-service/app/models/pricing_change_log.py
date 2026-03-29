import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from mediride_common.database.base import Base


class PricingChangeLog(Base):
    __tablename__ = "pricing_change_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    log_number: Mapped[int] = mapped_column(Integer, nullable=False)
    admin_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    admin_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    change_description: Mapped[str] = mapped_column(String(500), nullable=False)
    before_value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    after_value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
