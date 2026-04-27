"""Client for communicating with user-service."""
import logging
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)


class UserServiceClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def get_user_email(self, user_id: UUID) -> dict | None:
        """Get user email and name for notifications."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/users/{user_id}/profile",
                    headers={"X-Internal-Service": "notification-service"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "email": data.get("email"),
                        "name": f"{data.get('first_name', '')} {data.get('last_name', '')}".strip() or "User",
                    }
                return None
        except Exception as e:
            logger.error(f"Error fetching user email: {e}")
            return None

    async def get_driver_profile(self, driver_id: UUID) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/drivers/{driver_id}/profile",
                    headers={"X-Internal-Service": "notification-service"},
                )
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception as e:
            logger.error(f"Error fetching driver profile: {e}")
            return None
