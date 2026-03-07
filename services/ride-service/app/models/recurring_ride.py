import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Integer,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from mediride_common.database.base import Base


class RecurringRide(Base):
    __tablename__ = "recurring_rides"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rider_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    pickup_address: Mapped[str] = mapped_column(Text, nullable=False)
    destination_address: Mapped[str] = mapped_column(Text, nullable=False)
    ride_type: Mapped[str] = mapped_column(String(20), nullable=False)
    scheduled_time: Mapped[time] = mapped_column(Time, nullable=False)
    days_of_week: Mapped[list[int] | None] = mapped_column(
        ARRAY(item_type=Integer), nullable=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
