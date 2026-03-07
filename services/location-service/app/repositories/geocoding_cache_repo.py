from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geocoding_cache import GeocodingCache
from mediride_common.utils import utc_now


class GeocodingCacheRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_address(self, address: str) -> GeocodingCache | None:
        result = await self.session.execute(
            select(GeocodingCache).where(
                func.lower(GeocodingCache.address) == address.lower(),
                GeocodingCache.expires_at > utc_now(),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, entry: GeocodingCache) -> GeocodingCache:
        self.session.add(entry)
        await self.session.flush()
        return entry
