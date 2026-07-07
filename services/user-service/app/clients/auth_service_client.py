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

    async def delete_account(self, user_id: UUID) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.delete(
                    f"{self.base_url}/internal/users/{user_id}",
                    headers=HEADERS,
                )
                return resp.status_code == 200
        except httpx.RequestError as e:
            logger.error(f"Auth service delete error: {e}")
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

    async def get_is_active(self, user_id: UUID) -> bool | None:
        """Return the credential's active flag, or None if unavailable.

        Used to detect a driver still pending reactivation after an email change.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/users/{user_id}/reactivation-status",
                    headers=HEADERS,
                )
                if resp.status_code == 200:
                    return resp.json().get("is_active")
                return None
        except httpx.RequestError as e:
            logger.error(f"Auth service reactivation-status error: {e}")
            return None

    async def resend_reactivation(self, user_id: UUID) -> str:
        """Mint a fresh reactivation token for a pending driver.

        Returns the token. Raises RuntimeError if the account is already active
        or the auth service is unreachable.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.base_url}/internal/users/{user_id}/resend-reactivation",
                    headers=HEADERS,
                )
                if resp.status_code == 200:
                    return resp.json()["reactivation_token"]
                error_msg = "Failed to resend reactivation email"
                try:
                    body = resp.json()
                    error_msg = body.get("detail") or body.get("message") or error_msg
                except Exception:
                    pass
                raise RuntimeError(error_msg)
        except httpx.RequestError as e:
            logger.error(f"Auth service resend-reactivation error: {e}")
            raise RuntimeError(f"Auth service unavailable: {e}")

    async def change_email(self, user_id: UUID, new_email: str) -> str:
        """Change a driver's login email and deactivate the account pending reactivation.

        Returns a signed reactivation token used to build the link emailed to the
        new address. Raises RuntimeError on failure (e.g. email already in use).
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.put(
                    f"{self.base_url}/internal/users/{user_id}/change-email",
                    json={"new_email": new_email},
                    headers=HEADERS,
                )
                if resp.status_code == 200:
                    return resp.json()["reactivation_token"]
                error_msg = "Failed to change driver email"
                try:
                    body = resp.json()
                    error_msg = body.get("detail") or body.get("message") or error_msg
                except Exception:
                    pass
                logger.warning(
                    f"Auth service change-email returned {resp.status_code}: {resp.text}"
                )
                raise RuntimeError(error_msg)
        except httpx.RequestError as e:
            logger.error(f"Auth service change-email error: {e}")
            raise RuntimeError(f"Auth service unavailable: {e}")
