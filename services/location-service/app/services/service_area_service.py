import logging

from app.repositories.service_area_repo import ServiceAreaRepository

logger = logging.getLogger(__name__)


class ServiceAreaService:
    def __init__(self, repo: ServiceAreaRepository):
        self.repo = repo

    async def is_in_service_area(self, latitude: float, longitude: float) -> bool:
        """Check if a location is within any active service area."""
        area = await self.repo.get_containing_area(latitude, longitude)
        return area is not None

    async def get_service_area(self, latitude: float, longitude: float) -> dict | None:
        """Get the service area containing the given location."""
        area = await self.repo.get_containing_area(latitude, longitude)
        if not area:
            return None
        return {
            "id": str(area.id),
            "name": area.name,
            "is_active": area.is_active,
        }
