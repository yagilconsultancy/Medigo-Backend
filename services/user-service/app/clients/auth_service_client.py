import logging
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)

HEADERS = {"X-Internal-Service": "user-service"}


class AuthServiceClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def create_driver_credential(
        self, email: str, phone: str | None, password: str, business_id: UUID
    ) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.base_url}/internal/drivers/create-credential",
                    json={
                        "email": email,
                        "phone": phone,
                        "password": password,
                        "business_id": str(business_id),
                    },
                    headers=HEADERS,
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(
                    f"Auth service create-credential returned {resp.status_code}: {resp.text}"
                )
                return None
        except httpx.RequestError as e:
            logger.error(f"Auth service create-credential error: {e}")
            return None

    async def deactivate_account(self, user_id: UUID) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.put(
                    f"{self.base_url}/internal/users/{user_id}/deactivate",
                    headers=HEADERS,
                )
                return resp.status_code == 200
        except httpx.RequestError as e:
            logger.error(f"Auth service deactivate error: {e}")
            return False

    async def reactivate_account(self, user_id: UUID) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.put(
                    f"{self.base_url}/internal/users/{user_id}/reactivate",
                    headers=HEADERS,
                )
                return resp.status_code == 200
        except httpx.RequestError as e:
            logger.error(f"Auth service reactivate error: {e}")
            return False
