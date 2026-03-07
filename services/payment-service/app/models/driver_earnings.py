import uuid
from datetime import datetime
from sqlalchemy import DateTime, Numeric, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from mediride_common.database.base import Base

class DriverEarnings(Base):
    __tablename__ = "driver_earnings"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    driver_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, unique=True, index=True)
    available_balance: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    total_earned: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    total_withdrawn: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    pending_withdrawal: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
