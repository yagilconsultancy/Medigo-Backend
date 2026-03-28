import logging

import httpx

logger = logging.getLogger(__name__)

_HEADERS = {"X-Internal-Service": "payment-service"}


class LocationServiceClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def calculate_distance(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
    ) -> dict | None:
        """Call location-service to get driving distance and duration."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/locations/distance",
                    headers=_HEADERS,
                    params={
                        "origin_lat": origin_lat,
                        "origin_lng": origin_lng,
                        "dest_lat": dest_lat,
                        "dest_lng": dest_lng,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if "error" not in data:
                        return data
                    logger.warning("Location-service distance error: %s", data["error"])
                    return None
                logger.warning("Failed to calculate distance: %s", resp.status_code)
                return None
        except httpx.RequestError as e:
            logger.error("Error calling location-service for distance: %s", e)
            return None

    async def geocode(self, address: str) -> dict | None:
        """Call location-service to geocode an address to lat/lng."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/locations/geocode",
                    headers=_HEADERS,
                    params={"address": address},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if "error" not in data:
                        return data
                    logger.warning("Location-service geocode error: %s", data["error"])
                    return None
                logger.warning("Failed to geocode address: %s", resp.status_code)
                return None
        except httpx.RequestError as e:
            logger.error("Error calling location-service for geocode: %s", e)
            return None
