import logging
from datetime import timedelta

import googlemaps

from app.config import settings
from app.models.geocoding_cache import GeocodingCache
from app.repositories.geocoding_cache_repo import GeocodingCacheRepository
from mediride_common.utils import utc_now

logger = logging.getLogger(__name__)


class GeocodingService:
    def __init__(
        self,
        cache_repo: GeocodingCacheRepository,
        gmaps_client: googlemaps.Client | None,
    ):
        self.cache_repo = cache_repo
        self.gmaps = gmaps_client

    async def geocode(self, address: str) -> dict | None:
        """Convert address to lat/lng with caching."""
        # Check cache first
        cached = await self.cache_repo.get_by_address(address)
        if cached:
            return {
                "latitude": float(cached.latitude),
                "longitude": float(cached.longitude),
                "formatted_address": cached.formatted_address,
                "place_id": cached.place_id,
                "source": "cache",
            }

        if not self.gmaps:
            logger.warning("Google Maps client not configured")
            return None

        try:
            results = self.gmaps.geocode(address)
            if not results:
                return None

            result = results[0]
            location = result["geometry"]["location"]

            # Cache the result
            cache_entry = GeocodingCache(
                address=address,
                latitude=location["lat"],
                longitude=location["lng"],
                formatted_address=result.get("formatted_address", address),
                place_id=result.get("place_id"),
                expires_at=utc_now() + timedelta(hours=settings.GEOCODING_CACHE_TTL_HOURS),
            )
            await self.cache_repo.create(cache_entry)

            return {
                "latitude": location["lat"],
                "longitude": location["lng"],
                "formatted_address": result.get("formatted_address", address),
                "place_id": result.get("place_id"),
                "source": "google",
            }
        except Exception as e:
            logger.error(f"Geocoding failed for '{address}': {e}")
            return None

    async def reverse_geocode(self, latitude: float, longitude: float) -> dict | None:
        """Convert lat/lng to address."""
        if not self.gmaps:
            logger.warning("Google Maps client not configured")
            return None

        try:
            results = self.gmaps.reverse_geocode((latitude, longitude))
            if not results:
                return None

            result = results[0]
            return {
                "formatted_address": result.get("formatted_address", ""),
                "place_id": result.get("place_id"),
                "latitude": latitude,
                "longitude": longitude,
            }
        except Exception as e:
            logger.error(f"Reverse geocoding failed for ({latitude}, {longitude}): {e}")
            return None

    async def autocomplete(
        self, query: str, latitude: float | None = None, longitude: float | None = None
    ) -> list[dict]:
        """Address autocomplete suggestions."""
        if not self.gmaps:
            logger.warning("Google Maps client not configured")
            return []

        try:
            location = None
            if latitude is not None and longitude is not None:
                location = (latitude, longitude)

            predictions = self.gmaps.places_autocomplete(
                query,
                location=location,
                radius=50000,  # 50km radius bias
                types="address",
            )

            return [
                {
                    "description": p.get("description", ""),
                    "place_id": p.get("place_id", ""),
                    "main_text": p.get("structured_formatting", {}).get("main_text", ""),
                    "secondary_text": p.get("structured_formatting", {}).get("secondary_text", ""),
                }
                for p in predictions
            ]
        except Exception as e:
            logger.error(f"Autocomplete failed for '{query}': {e}")
            return []

    async def place_details(self, place_id: str) -> dict | None:
        """Get detailed place information."""
        if not self.gmaps:
            logger.warning("Google Maps client not configured")
            return None

        try:
            result = self.gmaps.place(
                place_id,
                fields=["formatted_address", "geometry", "name", "place_id", "type"],
            )
            place = result.get("result")
            if not place:
                return None

            location = place.get("geometry", {}).get("location", {})
            return {
                "name": place.get("name", ""),
                "formatted_address": place.get("formatted_address", ""),
                "place_id": place.get("place_id", ""),
                "latitude": location.get("lat"),
                "longitude": location.get("lng"),
                "types": place.get("types", []),
            }
        except Exception as e:
            logger.error(f"Place details failed for '{place_id}': {e}")
            return None
