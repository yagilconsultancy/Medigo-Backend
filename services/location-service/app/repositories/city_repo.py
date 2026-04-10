from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.city import City


class CityRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, city: City) -> City:
        self.session.add(city)
        await self.session.flush()
        await self.session.refresh(city)
        return city

    async def get_by_id(self, city_id: UUID) -> City | None:
        result = await self.session.execute(
            select(City).where(City.id == city_id)
        )
        return result.scalar_one_or_none()

    async def get_all(self) -> list[City]:
        result = await self.session.execute(
            select(City).order_by(City.name)
        )
        return list(result.scalars().all())

    async def get_kpis(self) -> dict:
        result = await self.session.execute(
            select(
                func.count(City.id).filter(City.is_active.is_(True)).label("active_cities"),
                func.coalesce(func.sum(City.number_of_zones), 0).label("total_zones"),
                func.count(City.id).filter(City.is_active.is_(True)).label("cities_online"),
                func.count(City.id).filter(City.is_active.is_(False)).label("inactive_cities"),
            )
        )
        row = result.one()
        return {
            "active_cities": row.active_cities or 0,
            "total_zones": int(row.total_zones),
            "cities_online": row.cities_online or 0,
            "inactive_cities": row.inactive_cities or 0,
        }

    async def update(self, city: City) -> City:
        await self.session.flush()
        await self.session.refresh(city)
        return city

    async def delete(self, city_id: UUID) -> None:
        city = await self.get_by_id(city_id)
        if city:
            await self.session.delete(city)
            await self.session.flush()
