import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from mediride_common.database.base import Base
from mediride_common.schemas.enums import WithdrawalStatus

class Withdrawal(Base):
    __tablename__ = "withdrawals"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    driver_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    transaction_fee: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    net_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    payment_method_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("payment_methods.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=WithdrawalStatus.PENDING)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
