import logging
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)


class RideServiceClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def get_ride(self, ride_id: UUID) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/rides/{ride_id}",
                    headers={"X-Internal-Service": "payment-service"},
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(f"Failed to fetch ride {ride_id}: {resp.status_code}")
                return None
        except httpx.RequestError as e:
            logger.error(f"Error calling ride-service for ride {ride_id}: {e}")
            return None

    async def get_guest_session(self, session_id: UUID) -> dict | None:
        """Fetch a guest booking session from ride-service."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/rides/public/guest-sessions/{session_id}",
                    headers={"X-Internal-Service": "payment-service"},
                )
                if resp.status_code == 200:
                    body = resp.json()
                    return body.get("data", body)
                logger.warning(f"Failed to fetch guest session {session_id}: {resp.status_code}")
                return None
        except httpx.RequestError as e:
            logger.error(f"Error calling ride-service for guest session {session_id}: {e}")
            return None

    async def update_ride_fare(self, ride_id: UUID, final_fare: float) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.put(
                    f"{self.base_url}/internal/rides/{ride_id}/fare",
                    headers={"X-Internal-Service": "payment-service"},
                    json={"final_fare": final_fare},
                )
                return resp.status_code == 200
        except httpx.RequestError as e:
            logger.error(f"Error updating ride fare {ride_id}: {e}")
            return False
