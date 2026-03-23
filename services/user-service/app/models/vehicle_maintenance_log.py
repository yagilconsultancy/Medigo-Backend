import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mediride_common.database.base import Base


class VehicleMaintenanceLog(Base):
    __tablename__ = "vehicle_maintenance_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False, index=True
    )
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    completed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    vehicle = relationship("Vehicle", back_populates="maintenance_logs")
