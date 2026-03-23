import asyncio
import logging
from uuid import UUID

from app.clients.user_service_client import UserServiceClient
from app.repositories.admin_transaction_repo import AdminTransactionRepository
from app.repositories.fare_repo import FareBreakdownRepository

logger = logging.getLogger(__name__)


class AdminTransactionService:
    def __init__(
        self,
        tx_repo: AdminTransactionRepository,
        fare_repo: FareBreakdownRepository,
        user_client: UserServiceClient,
    ):
        self.tx_repo = tx_repo
        self.fare_repo = fare_repo
        self.user_client = user_client

    async def get_transaction_kpis(self) -> dict:
        return await self.tx_repo.get_transaction_kpis()

    async def get_payment_method_breakdown(self) -> list[dict]:
        return await self.tx_repo.get_payment_method_breakdown()

    async def get_all_transactions(
        self,
        status_filter: str | None,
        search: str | None,
        page: int,
        limit: int,
    ) -> tuple[list[dict], int]:
        offset = (page - 1) * limit
        transactions, total = await self.tx_repo.get_all_transactions(
            status_filter=status_filter,
            search=search,
            offset=offset,
            limit=limit,
        )

        # Collect unique user_ids for enrichment
        user_ids: set[UUID] = set()
        for tx in transactions:
            user_ids.add(tx.user_id)
            if tx.ride_id:
                # We'll enrich ride info from fare breakdown
                pass

        # Fetch user profiles concurrently
        user_map: dict[str, dict] = {}

        async def _fetch_user(uid: UUID):
            profile = await self.user_client.get_user_profile(uid)
            if profile:
                user_map[str(uid)] = profile

        await asyncio.gather(*[_fetch_user(uid) for uid in user_ids])

        # Fetch fare breakdowns for ride_type info
        fare_map: dict[str, dict] = {}
        for tx in transactions:
            if tx.ride_id:
                fb = await self.fare_repo.get_by_ride_id(tx.ride_id)
                if fb:
                    fare_map[str(tx.ride_id)] = {
                        "ride_type": fb.ride_type,
                        "driver_id": str(fb.driver_id) if fb.driver_id else None,
                    }

        # Enrich driver names
        driver_ids: set[UUID] = set()
        for fb_data in fare_map.values():
            if fb_data.get("driver_id"):
                did = UUID(fb_data["driver_id"])
                if str(did) not in user_map:
                    driver_ids.add(did)

        await asyncio.gather(*[_fetch_user(uid) for uid in driver_ids])

        # Build response
        items = []
        for tx in transactions:
            user_profile = user_map.get(str(tx.user_id), {})
            rider_name = f"{user_profile.get('first_name', '')} {user_profile.get('last_name', '')}".strip() or "Unknown"

            driver_name = None
            ride_type = None
            fb_data = fare_map.get(str(tx.ride_id), {}) if tx.ride_id else {}
            if fb_data.get("driver_id"):
                dp = user_map.get(fb_data["driver_id"], {})
                driver_name = f"{dp.get('first_name', '')} {dp.get('last_name', '')}".strip() or None
            ride_type = fb_data.get("ride_type")

            items.append({
                "id": tx.id,
                "ride_id": tx.ride_id,
                "rider_name": rider_name,
                "driver_name": driver_name,
                "ride_type": ride_type,
                "amount": float(tx.amount),
                "payment_method": None,
                "status": tx.status,
                "transaction_type": tx.transaction_type,
                "created_at": tx.created_at,
            })

        return items, total
