import logging

import httpx

logger = logging.getLogger(__name__)


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
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/locations/distance",
                    headers={"X-Internal-Service": "tracking-service"},
                    params={
                        "origin_lat": origin_lat,
                        "origin_lng": origin_lng,
                        "dest_lat": dest_lat,
                        "dest_lng": dest_lng,
                    },
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(f"Failed to calculate distance: {resp.status_code}")
                return None
        except httpx.RequestError as e:
            logger.error(f"Error calling location-service: {e}")
            return None
