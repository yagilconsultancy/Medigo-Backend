import logging
from uuid import UUID

from app.models.city import City
from app.repositories.city_repo import CityRepository
from app.schemas.city import CityKPIs, CityRow

logger = logging.getLogger(__name__)


class CityService:
    def __init__(self, city_repo: CityRepository):
        self.city_repo = city_repo

    async def get_kpis(self) -> CityKPIs:
        """Get city KPI cards."""
        kpis_data = await self.city_repo.get_kpis()
        return CityKPIs(**kpis_data)

    async def list_cities(self) -> list[CityRow]:
        """List all cities with enriched data."""
        cities = await self.city_repo.get_all()

        rows = []
        for city in cities:
            # TODO: Fetch actual stats from user-service and ride-service
            # For now, return placeholder values
            rows.append(
                CityRow(
                    id=city.id,
                    name=city.name,
                    province=city.province,
                    service_zones=city.number_of_zones,
                    drivers=0,  # TODO: Fetch from user-service
                    riders=0,  # TODO: Fetch from user-service
                    total_trips=0,  # TODO: Fetch from ride-service
                    is_active=city.is_active,
                )
            )

        return rows

    async def create_city(
        self, name: str, province: str, number_of_zones: int
    ) -> City:
        """Create a new city."""
        city = City(name=name, province=province, number_of_zones=number_of_zones)
        return await self.city_repo.create(city)

    async def get_city(self, city_id: UUID) -> City:
        """Get city by ID."""
        city = await self.city_repo.get_by_id(city_id)
        if not city:
            raise ValueError("City not found")
        return city

    async def update_city(
        self,
        city_id: UUID,
        name: str | None = None,
        province: str | None = None,
        number_of_zones: int | None = None,
        is_active: bool | None = None,
    ) -> City:
        """Update city information."""
        city = await self.get_city(city_id)

        if name is not None:
            city.name = name
        if province is not None:
            city.province = province
        if number_of_zones is not None:
            city.number_of_zones = number_of_zones
        if is_active is not None:
            city.is_active = is_active

        return await self.city_repo.update(city)

    async def toggle_city_status(self, city_id: UUID, is_active: bool) -> City:
        """Toggle city active status."""
        return await self.update_city(city_id, is_active=is_active)

    async def delete_city(self, city_id: UUID) -> None:
        """Delete a city."""
        await self.city_repo.delete(city_id)
