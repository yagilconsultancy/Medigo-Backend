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
    ) -> dict:
        """Create driver credential. Returns result dict or raises with actual error."""
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
                # Extract the actual error message from auth-service
                error_msg = "Failed to create driver credential"
                try:
                    body = resp.json()
                    if body.get("message"):
                        error_msg = body["message"]
                    elif body.get("detail"):
                        error_msg = body["detail"]
                except Exception:
                    pass
                logger.warning(
                    f"Auth service create-credential returned {resp.status_code}: {resp.text}"
                )
                raise RuntimeError(error_msg)
        except httpx.RequestError as e:
            logger.error(f"Auth service create-credential error: {e}")
            raise RuntimeError(f"Auth service unavailable: {e}")

    async def create_admin_credential(
        self, email: str, password: str
    ) -> dict:
        """Create admin credential. Returns result dict or raises with actual error."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.base_url}/internal/admins/create-credential",
                    json={
                        "email": email,
                        "password": password,
                    },
                    headers=HEADERS,
                )
                if resp.status_code == 200:
                    return resp.json()
                error_msg = "Failed to create admin credential"
                try:
                    body = resp.json()
                    if body.get("message"):
                        error_msg = body["message"]
                    elif body.get("detail"):
                        error_msg = body["detail"]
                except Exception:
                    pass
                logger.warning(
                    f"Auth service create-admin-credential returned {resp.status_code}: {resp.text}"
                )
                raise RuntimeError(error_msg)
        except httpx.RequestError as e:
            logger.error(f"Auth service create-admin-credential error: {e}")
            raise RuntimeError(f"Auth service unavailable: {e}")

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
