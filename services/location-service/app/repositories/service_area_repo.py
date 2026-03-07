from geoalchemy2.functions import ST_Contains, ST_GeomFromText
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service_area import ServiceArea


class ServiceAreaRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_containing_area(self, latitude: float, longitude: float) -> ServiceArea | None:
        point_wkt = f"POINT({longitude} {latitude})"
        result = await self.session.execute(
            select(ServiceArea).where(
                ServiceArea.is_active.is_(True),
                ST_Contains(
                    ServiceArea.boundary,
                    ST_GeomFromText(point_wkt, 4326),
                ),
            ).limit(1)
        )
        return result.scalar_one_or_none()
