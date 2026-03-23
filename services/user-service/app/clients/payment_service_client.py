import logging
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)


class PaymentServiceClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def get_fleet_revenue(
        self, business_id: UUID | None = None, days: int = 30
    ) -> dict | None:
        try:
            params: dict = {"days": days}
            if business_id:
                params["business_id"] = str(business_id)

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/payments/fleet-revenue-summary",
                    params=params,
                    headers={"X-Internal-Service": "user-service"},
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(
                    f"Payment service fleet revenue returned {resp.status_code}"
                )
                return None
        except httpx.RequestError as e:
            logger.error(f"Payment service fleet revenue error: {e}")
            return None

    async def get_fleet_revenue_trend(
        self, business_id: UUID | None = None, days: int = 30
    ) -> list[dict]:
        try:
            params: dict = {"days": days}
            if business_id:
                params["business_id"] = str(business_id)

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/payments/fleet-revenue-trend",
                    params=params,
                    headers={"X-Internal-Service": "user-service"},
                )
                if resp.status_code == 200:
                    return resp.json().get("trend", [])
                logger.warning(
                    f"Payment service fleet trend returned {resp.status_code}"
                )
                return []
        except httpx.RequestError as e:
            logger.error(f"Payment service fleet trend error: {e}")
            return []

    async def get_fleet_earnings_breakdown(
        self, business_ids: list[UUID], days: int = 30
    ) -> dict:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/internal/payments/fleet-earnings-breakdown",
                    json={
                        "business_ids": [str(bid) for bid in business_ids],
                        "days": days,
                    },
                    headers={"X-Internal-Service": "user-service"},
                )
                if resp.status_code == 200:
                    return resp.json().get("breakdowns", {})
                logger.warning(
                    f"Payment service fleet breakdown returned {resp.status_code}"
                )
                return {}
        except httpx.RequestError as e:
            logger.error(f"Payment service fleet breakdown error: {e}")
            return {}
