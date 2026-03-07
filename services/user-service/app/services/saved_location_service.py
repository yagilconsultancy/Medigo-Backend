import logging
from uuid import UUID

from app.models.saved_location import SavedLocation
from app.repositories.saved_location_repo import SavedLocationRepository
from mediride_common.exceptions import ConflictError, NotFoundError, ValidationError
from mediride_common.schemas.enums import LocationType

logger = logging.getLogger(__name__)

MAX_SAVED_LOCATIONS = 20


class SavedLocationService:
    def __init__(self, repo: SavedLocationRepository):
        self.repo = repo

    async def create_location(self, user_id: UUID, **kwargs) -> SavedLocation:
        count = await self.repo.count_by_user(user_id)
        if count >= MAX_SAVED_LOCATIONS:
            raise ValidationError(
                f"Maximum of {MAX_SAVED_LOCATIONS} saved locations reached"
            )

        location_type = kwargs.get("location_type")
        if location_type in (LocationType.HOME, LocationType.WORK):
            existing = await self.repo.get_by_user_and_type(user_id, location_type)
            if existing:
                raise ConflictError(
                    f"A {location_type} location already exists. Update it instead."
                )

        lat = kwargs.get("latitude")
        lon = kwargs.get("longitude")
        if (lat is None) != (lon is None):
            raise ValidationError(
                "Both latitude and longitude must be provided together"
            )

        if kwargs.get("is_default"):
            await self.repo.clear_default(user_id)

        location = SavedLocation(
            user_id=user_id,
            sort_order=count,
            **kwargs,
        )
        return await self.repo.create(location)

    async def get_location(self, location_id: UUID, user_id: UUID) -> SavedLocation:
        location = await self.repo.get_by_id(location_id)
        if not location or location.user_id != user_id:
            raise NotFoundError("Saved location not found")
        return location

    async def list_locations(self, user_id: UUID) -> list[SavedLocation]:
        return await self.repo.list_by_user(user_id)

    async def update_location(
        self, location_id: UUID, user_id: UUID, **kwargs
    ) -> SavedLocation:
        location = await self.repo.get_by_id(location_id)
        if not location or location.user_id != user_id:
            raise NotFoundError("Saved location not found")

        location_type = kwargs.get("location_type")
        if location_type and location_type != location.location_type:
            if location_type in (LocationType.HOME, LocationType.WORK):
                existing = await self.repo.get_by_user_and_type(user_id, location_type)
                if existing and existing.id != location_id:
                    raise ConflictError(
                        f"A {location_type} location already exists"
                    )

        lat = kwargs.get("latitude", location.latitude)
        lon = kwargs.get("longitude", location.longitude)
        if (lat is None) != (lon is None):
            raise ValidationError(
                "Both latitude and longitude must be provided together"
            )

        if kwargs.get("is_default"):
            await self.repo.clear_default(user_id)

        await self.repo.update(location_id, **kwargs)
        return await self.repo.get_by_id(location_id)

    async def delete_location(self, location_id: UUID, user_id: UUID) -> None:
        location = await self.repo.get_by_id(location_id)
        if not location or location.user_id != user_id:
            raise NotFoundError("Saved location not found")
        await self.repo.delete(location_id)
        logger.info(f"Deleted saved location {location_id} for user {user_id}")

    async def reorder_locations(
        self, user_id: UUID, location_ids: list[UUID]
    ) -> list[SavedLocation]:
        existing = await self.repo.list_by_user(user_id)
        existing_ids = {loc.id for loc in existing}
        provided_ids = set(location_ids)

        if provided_ids != existing_ids:
            raise ValidationError(
                "Location IDs must match exactly the user's saved locations"
            )

        await self.repo.update_sort_orders(user_id, location_ids)
        return await self.repo.list_by_user(user_id)
