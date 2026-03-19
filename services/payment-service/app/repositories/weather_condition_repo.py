from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.weather_condition import WeatherCondition
from mediride_common.utils import utc_now


class WeatherConditionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_conditions(self) -> list[WeatherCondition]:
        result = await self.session.execute(
            select(WeatherCondition).where(WeatherCondition.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def get_all(self) -> list[WeatherCondition]:
        result = await self.session.execute(
            select(WeatherCondition).order_by(WeatherCondition.condition_type)
        )
        return list(result.scalars().all())

    async def get_by_id(self, condition_id: UUID) -> WeatherCondition | None:
        result = await self.session.execute(
            select(WeatherCondition).where(WeatherCondition.id == condition_id)
        )
        return result.scalar_one_or_none()

    async def toggle(
        self,
        condition_type: str,
        is_active: bool,
        activated_by: UUID,
        notes: str | None = None,
    ) -> WeatherCondition | None:
        result = await self.session.execute(
            select(WeatherCondition).where(
                WeatherCondition.condition_type == condition_type
            )
        )
        condition = result.scalar_one_or_none()
        if not condition:
            return None

        now = utc_now()
        condition.is_active = is_active
        condition.activated_by = activated_by
        condition.notes = notes
        if is_active:
            condition.activated_at = now
            condition.deactivated_at = None
        else:
            condition.deactivated_at = now
        await self.session.flush()
        await self.session.refresh(condition)
        return condition
