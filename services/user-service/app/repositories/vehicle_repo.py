from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.vehicle import Vehicle
from app.models.vehicle_maintenance_log import VehicleMaintenanceLog


class VehicleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, vehicle: Vehicle) -> Vehicle:
        self.session.add(vehicle)
        await self.session.flush()
        await self.session.refresh(vehicle)
        return vehicle

    async def get_by_id(self, vehicle_id: UUID) -> Vehicle | None:
        result = await self.session.execute(
            select(Vehicle)
            .options(selectinload(Vehicle.maintenance_logs))
            .where(Vehicle.id == vehicle_id, Vehicle.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_plate(self, plate_number: str) -> Vehicle | None:
        result = await self.session.execute(
            select(Vehicle).where(
                Vehicle.plate_number == plate_number,
                Vehicle.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_vin(self, vin: str) -> Vehicle | None:
        result = await self.session.execute(
            select(Vehicle).where(
                Vehicle.vin == vin,
                Vehicle.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        business_id: UUID | None = None,
        status_filter: str | None = None,
        category_filter: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Vehicle], int]:
        conditions = [Vehicle.deleted_at.is_(None)]

        if business_id:
            conditions.append(Vehicle.business_id == business_id)
        if status_filter:
            conditions.append(Vehicle.status == status_filter)
        if category_filter:
            conditions.append(Vehicle.category == category_filter)
        if search:
            pattern = f"%{search}%"
            conditions.append(
                or_(
                    Vehicle.make.ilike(pattern),
                    Vehicle.model.ilike(pattern),
                    Vehicle.plate_number.ilike(pattern),
                    Vehicle.vehicle_name.ilike(pattern),
                )
            )

        base_query = select(Vehicle).where(*conditions)

        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            base_query
            .order_by(desc(Vehicle.created_at))
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, vehicle_id: UUID, **kwargs) -> None:
        vehicle = await self.get_by_id(vehicle_id)
        if vehicle:
            for key, value in kwargs.items():
                setattr(vehicle, key, value)
            await self.session.flush()

    async def soft_delete(self, vehicle_id: UUID) -> None:
        vehicle = await self.get_by_id(vehicle_id)
        if vehicle:
            vehicle.deleted_at = datetime.now(timezone.utc)
            await self.session.flush()

    async def get_kpis(self, business_id: UUID | None = None) -> dict:
        conditions = [Vehicle.deleted_at.is_(None)]
        if business_id:
            conditions.append(Vehicle.business_id == business_id)

        result = await self.session.execute(
            select(
                func.count().label("total"),
                func.count().filter(Vehicle.status == "active").label("active"),
                func.count().filter(Vehicle.status == "maintenance").label("maintenance"),
                func.count().filter(Vehicle.status == "inactive").label("inactive"),
            ).where(*conditions)
        )
        row = result.one()
        return {
            "total_vehicles": row.total,
            "active": row.active,
            "maintenance": row.maintenance,
            "inactive": row.inactive,
        }

    async def count_by_business(self, business_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count()).where(
                Vehicle.business_id == business_id,
                Vehicle.deleted_at.is_(None),
            )
        )
        return result.scalar_one()

    async def get_by_driver(self, driver_profile_id: UUID) -> Vehicle | None:
        result = await self.session.execute(
            select(Vehicle).where(
                Vehicle.driver_profile_id == driver_profile_id,
                Vehicle.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def unassign_driver_from_all(self, driver_profile_id: UUID) -> None:
        """Remove driver assignment from all vehicles."""
        result = await self.session.execute(
            select(Vehicle).where(
                Vehicle.driver_profile_id == driver_profile_id,
                Vehicle.deleted_at.is_(None),
            )
        )
        for vehicle in result.scalars().all():
            vehicle.driver_profile_id = None
        await self.session.flush()
