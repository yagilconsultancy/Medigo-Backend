import logging

import httpx

from mediride_common.exceptions import (
    AuthenticationError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
)

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10.0


class UserServiceClient:
    """HTTP client for communicating with user-service internal APIs."""

    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")

    async def verify_invite_token(self, token: str) -> dict:
        """Verify a driver invitation token. Returns invite details."""
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(
                    f"{self._base_url}/internal/invitations/verify",
                    params={"token": token},
                    headers={"X-Internal-Service": "auth-service"},
                )
        except httpx.ConnectError:
            raise ServiceUnavailableError("User service is unavailable")
        except httpx.TimeoutException:
            raise ServiceUnavailableError("User service request timed out")

        if response.status_code == 404:
            raise NotFoundError("Invalid or expired invitation token")
        if response.status_code == 400:
            raise ValidationError(response.json().get("detail", "Invalid invitation"))
        if response.status_code != 200:
            raise ServiceUnavailableError("Failed to verify invitation")

        return response.json()

    async def accept_invitation(self, token: str, user_id: str) -> dict:
        """Mark an invitation as accepted."""
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(
                    f"{self._base_url}/internal/invitations/accept",
                    json={"token": token, "user_id": user_id},
                    headers={"X-Internal-Service": "auth-service"},
                )
        except httpx.ConnectError:
            raise ServiceUnavailableError("User service is unavailable")
        except httpx.TimeoutException:
            raise ServiceUnavailableError("User service request timed out")

        if response.status_code != 200:
            logger.error(
                f"Failed to accept invitation: {response.status_code} {response.text}"
            )
            raise ServiceUnavailableError("Failed to accept invitation")

        return response.json()
