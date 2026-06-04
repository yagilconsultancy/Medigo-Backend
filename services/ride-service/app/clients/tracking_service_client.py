import logging
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)


class TrackingServiceClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def get_driver_location(self, ride_id: UUID) -> dict | None:
        """Fetch the driver's last known GPS position for a ride."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/tracking/internal/{ride_id}/driver-location",
                    headers={"X-Internal-Service": "ride-service"},
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(
                    f"Failed to fetch driver location for ride {ride_id}: {resp.status_code}"
                )
                return None
        except httpx.RequestError as e:
            logger.error(f"Error calling tracking-service for ride {ride_id}: {e}")
            return None
