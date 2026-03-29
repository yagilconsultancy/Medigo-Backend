from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vehicle import Vehicle
from app.models.vehicle_category_config import VehicleCategoryConfig


class VehicleCategoryConfigRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_all(self) -> list[VehicleCategoryConfig]:
        result = await self.session.execute(
            select(VehicleCategoryConfig).order_by(VehicleCategoryConfig.base_fare.asc())
        )
        return list(result.scalars().all())

    async def get_by_category(self, category: str) -> VehicleCategoryConfig | None:
        result = await self.session.execute(
            select(VehicleCategoryConfig).where(
                VehicleCategoryConfig.category == category
            )
        )
        return result.scalar_one_or_none()

    async def update(self, config_id: UUID, **kwargs) -> None:
        config = await self.session.get(VehicleCategoryConfig, config_id)
        if config:
            for key, value in kwargs.items():
                setattr(config, key, value)
            await self.session.flush()

    async def get_fleet_composition(self) -> dict:
        total_result = await self.session.execute(
            select(func.count()).where(Vehicle.deleted_at.is_(None))
        )
        total = total_result.scalar_one()

        result = await self.session.execute(
            select(Vehicle.category, func.count().label("count"))
            .where(Vehicle.deleted_at.is_(None))
            .group_by(Vehicle.category)
        )
        breakdown = []
        for category, count in result.all():
            # Get display name from config
            config = await self.get_by_category(category)
            display_name = config.display_name if config else category
            percentage = round((count / total * 100), 1) if total > 0 else 0.0
            breakdown.append({
                "category": category,
                "display_name": display_name,
                "count": count,
                "percentage": percentage,
            })

        return {"total_vehicles": total, "breakdown": breakdown}
