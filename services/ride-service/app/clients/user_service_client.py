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

    async def get_business(self, business_id: UUID) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/businesses/{business_id}",
                    headers={"X-Internal-Service": "ride-service"},
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(
                    f"Failed to fetch business {business_id}: {resp.status_code}"
                )
                return None
        except httpx.RequestError as e:
            logger.error(f"Error calling user-service for business {business_id}: {e}")
            return None

    async def get_business_drivers(self, business_id: UUID) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/businesses/{business_id}/drivers",
                    headers={"X-Internal-Service": "ride-service"},
                )
                if resp.status_code == 200:
                    return resp.json().get("drivers", [])
                return []
        except httpx.RequestError as e:
            logger.error(f"Error fetching drivers for business {business_id}: {e}")
            return []
