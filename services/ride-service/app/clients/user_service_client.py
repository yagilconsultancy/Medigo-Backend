import logging
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)


class UserServiceClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def get_user_profile(self, user_id: UUID) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/users/{user_id}/profile",
                    headers={"X-Internal-Service": "ride-service"},
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(
                    f"Failed to fetch user profile {user_id}: {resp.status_code}"
                )
                return None
        except httpx.RequestError as e:
            logger.error(f"Error calling user-service for user {user_id}: {e}")
            return None

    async def create_guest_rider(
        self,
        *,
        email: str | None = None,
        phone: str | None = None,
        full_name: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> dict | None:
        payload = {
            "email": email,
            "phone": phone,
            "full_name": full_name,
            "first_name": first_name,
            "last_name": last_name,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.base_url}/internal/guest-riders",
                    headers={"X-Internal-Service": "ride-service"},
                    json=payload,
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(
                    f"Failed to create guest rider profile: {resp.status_code} {resp.text}"
                )
                return None
        except httpx.RequestError as e:
            logger.error(f"Error creating guest rider profile: {e}")
            return None

    async def get_driver_profile(self, driver_id: UUID) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/drivers/{driver_id}/profile",
                    headers={"X-Internal-Service": "ride-service"},
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(
                    f"Failed to fetch driver profile {driver_id}: {resp.status_code}"
                )
                return None
        except httpx.RequestError as e:
            logger.error(f"Error calling user-service for driver {driver_id}: {e}")
            return None

    async def get_fleet(self, fleet_id: UUID) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/fleets/{fleet_id}",
                    headers={"X-Internal-Service": "ride-service"},
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(
                    f"Failed to fetch fleet {fleet_id}: {resp.status_code}"
                )
                return None
        except httpx.RequestError as e:
            logger.error(f"Error calling user-service for fleet {fleet_id}: {e}")
            return None

    async def get_fleet_drivers(self, fleet_id: UUID) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/fleets/{fleet_id}/drivers",
                    headers={"X-Internal-Service": "ride-service"},
                )
                if resp.status_code == 200:
                    return resp.json().get("drivers", [])
                return []
        except httpx.RequestError as e:
            logger.error(f"Error fetching drivers for fleet {fleet_id}: {e}")
            return []

    async def get_available_drivers(self) -> list[dict]:
        """Get all approved, active drivers for admin assignment."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/drivers/available",
                    headers={"X-Internal-Service": "ride-service"},
                )
                if resp.status_code == 200:
                    return resp.json().get("drivers", [])
                return []
        except httpx.RequestError as e:
            logger.error(f"Error fetching available drivers: {e}")
            return []

    async def get_facility_count(self) -> int:
        """Get count of registered facility users."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/facilities/count",
                    headers={"X-Internal-Service": "ride-service"},
                )
                if resp.status_code == 200:
                    return resp.json().get("count", 0)
                return 0
        except httpx.RequestError as e:
            logger.error(f"Error fetching facility count: {e}")
            return 0

    async def get_top_facilities(self, facility_ids: list) -> dict:
        """Batch get facility user details for analytics."""
        if not facility_ids:
            return {}
        try:
            ids_str = ",".join(str(fid) for fid in facility_ids)
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/facilities/top",
                    params={"facility_ids": ids_str},
                    headers={"X-Internal-Service": "ride-service"},
                )
                if resp.status_code == 200:
                    return resp.json().get("facilities", {})
                logger.warning(
                    f"Failed to fetch facility details: {resp.status_code}"
                )
                return {}
        except httpx.RequestError as e:
            logger.error(f"Error fetching facility details: {e}")
            return {}

    async def get_fleets_with_vehicle_counts(
        self, fleet_ids: list
    ) -> dict:
        """Batch get fleet names + vehicle counts for analytics."""
        if not fleet_ids:
            return {}
        try:
            ids_str = ",".join(str(fid) for fid in fleet_ids)
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/fleets/with-vehicle-counts",
                    params={"fleet_ids": ids_str},
                    headers={"X-Internal-Service": "ride-service"},
                )
                if resp.status_code == 200:
                    return resp.json().get("fleets", {})
                logger.warning(
                    f"Failed to fetch fleet vehicle counts: {resp.status_code}"
                )
                return {}
        except httpx.RequestError as e:
            logger.error(f"Error fetching fleet vehicle counts: {e}")
            return {}

    async def batch_get_users(self, user_ids: list[UUID]) -> list[dict]:
        """Batch get user details (id, first_name, last_name) for multiple users."""
        if not user_ids:
            return []
        try:
            ids_str = ",".join(str(uid) for uid in user_ids)
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/users/batch",
                    params={"user_ids": ids_str},
                    headers={"X-Internal-Service": "ride-service"},
                )
                if resp.status_code == 200:
                    return resp.json().get("users", [])
                logger.warning(
                    f"Failed to batch fetch users: {resp.status_code}"
                )
                return []
        except httpx.RequestError as e:
            logger.error(f"Error batch fetching users: {e}")
            return []

    async def search_user_ids(
        self, query: str, role: str | None = None
    ) -> list[UUID] | None:
        """Resolve a free-text person query to user IDs.

        Returns ``None`` — not ``[]`` — when the lookup itself fails, so callers
        can tell "user-service is down, search on my own columns only" apart from
        "nobody matched that name".
        """
        if not query.strip():
            return []
        try:
            params: dict[str, str] = {"q": query.strip()}
            if role:
                params["role"] = role
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/users/search",
                    params=params,
                    headers={"X-Internal-Service": "ride-service"},
                )
                if resp.status_code == 200:
                    return [
                        UUID(uid) for uid in resp.json().get("user_ids", [])
                    ]
                logger.warning(f"Failed to search users: {resp.status_code}")
                return None
        except (httpx.RequestError, ValueError) as e:
            logger.error(f"Error searching users: {e}")
            return None

    async def get_drivers_with_details(self, driver_ids: list[UUID]) -> list[dict]:
        """Batch get driver details with fleet info."""
        if not driver_ids:
            return []
        try:
            ids_str = ",".join(str(did) for did in driver_ids)
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/drivers/with-details",
                    params={"driver_ids": ids_str},
                    headers={"X-Internal-Service": "ride-service"},
                )
                if resp.status_code == 200:
                    return resp.json().get("drivers", [])
                logger.warning(
                    f"Failed to batch fetch drivers: {resp.status_code}"
                )
                return []
        except httpx.RequestError as e:
            logger.error(f"Error batch fetching drivers: {e}")
            return []
