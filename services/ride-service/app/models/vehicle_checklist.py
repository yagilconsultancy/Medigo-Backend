import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from mediride_common.database.base import Base


class VehicleChecklist(Base):
    __tablename__ = "vehicle_checklists"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    driver_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    checklist_date: Mapped[date] = mapped_column(Date, nullable=False)
    tires_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    brakes_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    lights_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    fluid_levels_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    wheelchair_ramp_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    stretcher_mount_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    first_aid_kit_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    fire_extinguisher_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    vehicle_clean: Mapped[bool] = mapped_column(Boolean, default=False)
    all_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
