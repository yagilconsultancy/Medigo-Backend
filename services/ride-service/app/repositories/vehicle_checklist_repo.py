from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vehicle_checklist import VehicleChecklist


class VehicleChecklistRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, checklist: VehicleChecklist) -> VehicleChecklist:
        self.session.add(checklist)
        await self.session.flush()
        await self.session.refresh(checklist)
        return checklist

    async def get_by_driver_date(self, driver_id: UUID, checklist_date: date) -> VehicleChecklist | None:
        result = await self.session.execute(
            select(VehicleChecklist).where(
                VehicleChecklist.driver_id == driver_id,
                VehicleChecklist.checklist_date == checklist_date,
            )
        )
        return result.scalar_one_or_none()

    async def get_recent_by_driver(self, driver_id: UUID, limit: int = 7) -> list[VehicleChecklist]:
        result = await self.session.execute(
            select(VehicleChecklist)
            .where(VehicleChecklist.driver_id == driver_id)
            .order_by(VehicleChecklist.checklist_date.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
