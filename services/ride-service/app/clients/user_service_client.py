import logging
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)


class UserServiceClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def get_user_profile(self, user_id: UUID) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/users/{user_id}/profile",
                    headers={"X-Internal-Service": "ride-service"},
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(
                    f"Failed to fetch user profile {user_id}: {resp.status_code}"
                )
                return None
        except httpx.RequestError as e:
            logger.error(f"Error calling user-service for user {user_id}: {e}")
            return None

    async def get_driver_profile(self, driver_id: UUID) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/drivers/{driver_id}/profile",
                    headers={"X-Internal-Service": "ride-service"},
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(
                    f"Failed to fetch driver profile {driver_id}: {resp.status_code}"
                )
                return None
        except httpx.RequestError as e:
            logger.error(f"Error calling user-service for driver {driver_id}: {e}")
            return None

    async def get_fleet(self, fleet_id: UUID) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/fleets/{fleet_id}",
                    headers={"X-Internal-Service": "ride-service"},
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(
                    f"Failed to fetch fleet {fleet_id}: {resp.status_code}"
                )
                return None
        except httpx.RequestError as e:
            logger.error(f"Error calling user-service for fleet {fleet_id}: {e}")
            return None

    async def get_fleet_drivers(self, fleet_id: UUID) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/fleets/{fleet_id}/drivers",
                    headers={"X-Internal-Service": "ride-service"},
                )
                if resp.status_code == 200:
                    return resp.json().get("drivers", [])
                return []
        except httpx.RequestError as e:
            logger.error(f"Error fetching drivers for fleet {fleet_id}: {e}")
            return []

    async def get_available_drivers(self) -> list[dict]:
        """Get all approved, active drivers for admin assignment."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/drivers/available",
                    headers={"X-Internal-Service": "ride-service"},
                )
                if resp.status_code == 200:
                    return resp.json().get("drivers", [])
                return []
        except httpx.RequestError as e:
            logger.error(f"Error fetching available drivers: {e}")
            return []

    async def get_fleets_with_vehicle_counts(
        self, fleet_ids: list
    ) -> dict:
        """Batch get fleet names + vehicle counts for analytics."""
        if not fleet_ids:
            return {}
        try:
            ids_str = ",".join(str(fid) for fid in fleet_ids)
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/fleets/with-vehicle-counts",
                    params={"fleet_ids": ids_str},
                    headers={"X-Internal-Service": "ride-service"},
                )
                if resp.status_code == 200:
                    return resp.json().get("fleets", {})
                logger.warning(
                    f"Failed to fetch fleet vehicle counts: {resp.status_code}"
                )
                return {}
        except httpx.RequestError as e:
            logger.error(f"Error fetching fleet vehicle counts: {e}")
            return {}
