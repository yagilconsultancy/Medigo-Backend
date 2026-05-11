"""Client for communicating with payment-service."""
import logging
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)
_HEADERS = {"X-Internal-Service": "notification-service"}


class PaymentServiceClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def get_receipt(self, ride_id: UUID, user_id: UUID) -> dict | None:
        """Get receipt details for a completed ride payment."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/payments/receipts/{ride_id}",
                    params={"user_id": str(user_id)},
                    headers=_HEADERS,
                )
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception as e:
            logger.error(f"Error fetching receipt for ride {ride_id}: {e}")
            return None
