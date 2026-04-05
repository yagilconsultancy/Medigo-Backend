import logging
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)

HEADERS = {"X-Internal-Service": "user-service"}


class RideServiceClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def get_driver_stats(self, driver_id: UUID) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/drivers/{driver_id}/stats",
                    headers=HEADERS,
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(
                    f"Ride service driver stats returned {resp.status_code}"
                )
                return None
        except httpx.RequestError as e:
            logger.error(f"Ride service driver stats error: {e}")
            return None

    async def get_driver_ratings(
        self, driver_id: UUID, limit: int = 10
    ) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/drivers/{driver_id}/ratings",
                    params={"limit": limit},
                    headers=HEADERS,
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(
                    f"Ride service driver ratings returned {resp.status_code}"
                )
                return None
        except httpx.RequestError as e:
            logger.error(f"Ride service driver ratings error: {e}")
            return None

    async def get_driver_completed_rides(
        self, driver_id: UUID, page: int = 1, limit: int = 20
    ) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/rides/driver/{driver_id}/completed",
                    params={"page": page, "limit": limit},
                    headers=HEADERS,
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(
                    f"Ride service driver completed rides returned {resp.status_code}"
                )
                return None
        except httpx.RequestError as e:
            logger.error(f"Ride service driver completed rides error: {e}")
            return None

    async def get_driver_dashboard_stats(self) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/drivers/dashboard-stats",
                    headers=HEADERS,
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(
                    f"Ride service driver dashboard stats returned {resp.status_code}"
                )
                return None
        except httpx.RequestError as e:
            logger.error(f"Ride service driver dashboard stats error: {e}")
            return None

    # --- Rider methods ---

    async def get_rider_stats(self, rider_id: UUID) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/riders/{rider_id}/stats",
                    headers=HEADERS,
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(f"Ride service rider stats returned {resp.status_code}")
                return None
        except httpx.RequestError as e:
            logger.error(f"Ride service rider stats error: {e}")
            return None

    async def get_rider_rides(
        self, rider_id: UUID, page: int = 1, limit: int = 20
    ) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/riders/{rider_id}/rides",
                    params={"page": page, "limit": limit},
                    headers=HEADERS,
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(f"Ride service rider rides returned {resp.status_code}")
                return None
        except httpx.RequestError as e:
            logger.error(f"Ride service rider rides error: {e}")
            return None

    async def get_batch_rider_activity(self, rider_ids: list[UUID]) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/internal/riders/batch-activity",
                    json={"rider_ids": [str(rid) for rid in rider_ids]},
                    headers=HEADERS,
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(
                    f"Ride service batch rider activity returned {resp.status_code}"
                )
                return None
        except httpx.RequestError as e:
            logger.error(f"Ride service batch rider activity error: {e}")
            return None
