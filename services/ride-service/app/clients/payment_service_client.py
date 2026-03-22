import logging
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)


class PaymentServiceClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def get_fare_breakdown(self, ride_id: UUID) -> dict | None:
        """Fetch fare breakdown from payment-service for a given ride."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/payments/receipts/{ride_id}",
                    headers={"X-Internal-Service": "ride-service"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("data")
                logger.warning(f"Failed to fetch fare for ride {ride_id}: {resp.status_code}")
                return None
        except httpx.RequestError as e:
            logger.error(f"Error calling payment-service for ride {ride_id}: {e}")
            return None

    async def get_revenue_summary(self, days: int = 30) -> dict | None:
        """Fetch revenue summary from payment-service for analytics dashboard."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/payments/revenue-summary",
                    params={"days": days},
                    headers={"X-Internal-Service": "ride-service"},
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(f"Failed to fetch revenue summary: {resp.status_code}")
                return None
        except httpx.RequestError as e:
            logger.error(f"Error calling payment-service for revenue summary: {e}")
            return None
