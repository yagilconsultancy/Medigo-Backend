import logging
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)


class RideServiceClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def get_ride(self, ride_id: UUID) -> dict | None:
        """Fetch ride details from ride-service."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/rides/{ride_id}",
                    headers={"X-Internal-Service": "tracking-service"},
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(f"Failed to fetch ride {ride_id}: {resp.status_code}")
                return None
        except httpx.RequestError as e:
            logger.error(f"Error calling ride-service for ride {ride_id}: {e}")
            return None

    async def get_active_rides(self) -> list[dict]:
        """Fetch all active transit rides from ride-service."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/rides/active",
                    headers={"X-Internal-Service": "tracking-service"},
                )
                if resp.status_code == 200:
                    return resp.json().get("rides", [])
                logger.warning(f"Failed to fetch active rides: {resp.status_code}")
                return []
        except httpx.RequestError as e:
            logger.error(f"Error calling ride-service for active rides: {e}")
            return []

    async def get_completed_today_count(self) -> int:
        """Fetch count of rides completed today from ride-service."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/rides/completed-today-count",
                    headers={"X-Internal-Service": "tracking-service"},
                )
                if resp.status_code == 200:
                    return resp.json().get("count", 0)
                return 0
        except httpx.RequestError as e:
            logger.error(f"Error calling ride-service for completed count: {e}")
            return 0
