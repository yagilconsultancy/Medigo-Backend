from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vehicle_maintenance_log import VehicleMaintenanceLog


class VehicleMaintenanceLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, log: VehicleMaintenanceLog) -> VehicleMaintenanceLog:
        self.session.add(log)
        await self.session.flush()
        await self.session.refresh(log)
        return log

    async def list_by_vehicle(self, vehicle_id: UUID) -> list[VehicleMaintenanceLog]:
        result = await self.session.execute(
            select(VehicleMaintenanceLog)
            .where(VehicleMaintenanceLog.vehicle_id == vehicle_id)
            .order_by(desc(VehicleMaintenanceLog.scheduled_date))
        )
        return list(result.scalars().all())
