import logging
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)


class PaymentServiceClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def estimate_ride(
        self,
        *,
        pickup_address: str,
        destination_address: str,
        scheduled_at: str,
        ride_type: str,
        trip_type: str,
        trip_structure: str,
        pickup_latitude: float | None = None,
        pickup_longitude: float | None = None,
        destination_latitude: float | None = None,
        destination_longitude: float | None = None,
        use_highway_407: bool = False,
        highway_407_route: str | None = None,
        is_dialysis_trip: bool = False,
    ) -> dict | None:
        """Fetch distance, duration, and fare estimate for a ride."""
        payload = {
            "pickup_address": pickup_address,
            "pickup_latitude": pickup_latitude,
            "pickup_longitude": pickup_longitude,
            "destination_address": destination_address,
            "destination_latitude": destination_latitude,
            "destination_longitude": destination_longitude,
            "scheduled_at": scheduled_at,
            "use_highway_407": use_highway_407,
            "highway_407_route": highway_407_route,
            "is_dialysis_trip": is_dialysis_trip,
            "ride_type": ride_type,
            "trip_type": trip_type,
            "trip_structure": trip_structure,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.base_url}/payments/fare-estimate",
                    json=payload,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("data")
                logger.warning(
                    "Failed to fetch ride estimate for %s -> %s: %s",
                    pickup_address,
                    destination_address,
                    resp.status_code,
                )
                return None
        except httpx.RequestError as e:
            logger.error(
                "Error calling payment-service for ride estimate %s -> %s: %s",
                pickup_address,
                destination_address,
                e,
            )
            return None

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
