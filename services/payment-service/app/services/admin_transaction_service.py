import asyncio
import logging
from uuid import UUID

from app.clients.ride_service_client import RideServiceClient
from app.clients.user_service_client import UserServiceClient
from app.repositories.admin_transaction_repo import AdminTransactionRepository
from app.repositories.fare_repo import FareBreakdownRepository

logger = logging.getLogger(__name__)

_PM_DISPLAY_NAMES = {
    "credit_card": "Credit Card",
    "debit_card": "Debit Card",
    "bank_account": "Direct Pay",
    "medicare": "Medicare",
    "medicaid": "Medicaid",
    "private_insurance": "Insurance",
}


def _booking_ref(ride_id) -> str | None:
    """Display reference for a ride, e.g. "BK-3F2A9C41".

    Derived from the ride id so it is stable across processes and restarts, and
    matches the format ride-service and notification-service already show to
    admins and riders.
    """
    if not ride_id:
        return None
    return f"BK-{str(ride_id)[:8].upper()}"


def _format_payment_method(pm) -> str | None:
    if not pm:
        return None
    if pm.brand and pm.last_four:
        return f"{pm.brand} **{pm.last_four}"
    display = _PM_DISPLAY_NAMES.get(pm.method_type)
    if display and pm.last_four:
        return f"{display} **{pm.last_four}"
    if display:
        return display
    return pm.method_type.replace("_", " ").title() if pm.method_type else None


class AdminTransactionService:
    def __init__(
        self,
        tx_repo: AdminTransactionRepository,
        fare_repo: FareBreakdownRepository,
        user_client: UserServiceClient,
        ride_client: RideServiceClient | None = None,
    ):
        self.tx_repo = tx_repo
        self.fare_repo = fare_repo
        self.user_client = user_client
        self.ride_client = ride_client

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

        # Fetch user profiles concurrently
        user_map: dict[str, dict] = {}

        async def _fetch_user(uid: UUID):
            profile = await self.user_client.get_user_profile(uid)
            if profile:
                user_map[str(uid)] = profile

        await asyncio.gather(*[_fetch_user(uid) for uid in user_ids])

        # Batch fetch default payment methods for all riders
        pm_map = await self.tx_repo.get_default_payment_methods_batch(list(user_ids))

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

            pm = pm_map.get(tx.user_id)
            payment_method_str = _format_payment_method(pm)

            items.append({
                "id": tx.id,
                "ride_id": tx.ride_id,
                "rider_name": rider_name,
                "driver_name": driver_name,
                "ride_type": ride_type,
                "amount": float(tx.amount),
                "payment_method": payment_method_str,
                "status": tx.status,
                "transaction_type": tx.transaction_type,
                "created_at": tx.created_at,
            })

        return items, total

    async def get_transaction_detail(self, tx_id: UUID) -> dict | None:
        tx = await self.tx_repo.get_by_id(tx_id)
        if not tx:
            return None

        # Get fare breakdown for ride info
        fb = None
        if tx.ride_id:
            fb = await self.fare_repo.get_by_ride_id(tx.ride_id)

        driver_id = fb.driver_id if fb and fb.driver_id else None

        # Fetch rider profile, driver profile, and ride details concurrently
        async def _get_rider():
            return await self.user_client.get_user_profile(tx.user_id)

        async def _get_driver():
            if driver_id:
                return await self.user_client.get_user_profile(driver_id)
            return None

        async def _get_ride():
            if tx.ride_id and self.ride_client:
                return await self.ride_client.get_ride(tx.ride_id)
            return None

        rider_profile, driver_profile, ride_data = await asyncio.gather(
            _get_rider(), _get_driver(), _get_ride()
        )

        # Get payment method for this rider
        pm = await self.tx_repo.get_payment_method_for_user(tx.user_id)

        # Build names
        rider_name = "Unknown"
        if rider_profile:
            rider_name = f"{rider_profile.get('first_name', '')} {rider_profile.get('last_name', '')}".strip() or "Unknown"

        driver_name = None
        if driver_profile:
            driver_name = f"{driver_profile.get('first_name', '')} {driver_profile.get('last_name', '')}".strip() or None

        # Build ride description
        ride_type = fb.ride_type if fb else None
        ride_description = None
        if ride_type:
            parts = [ride_type.replace("_", " ").title()]
            if fb and fb.distance_km:
                parts.append(f"{float(fb.distance_km)} km")
            ride_description = " - ".join(parts)

        # Route addresses from ride-service. The booking ref comes off the ride id
        # we already hold, so it survives ride-service being unreachable.
        pickup_address = None
        destination_address = None
        if ride_data:
            pickup_address = ride_data.get("pickup_address")
            destination_address = ride_data.get("destination_address")
        booking_ref = _booking_ref(tx.ride_id)

        return {
            "id": tx.id,
            "ride_id": tx.ride_id,
            "rider_name": rider_name,
            "driver_name": driver_name,
            "ride_type": ride_type,
            "ride_description": ride_description,
            "amount": float(tx.amount),
            "payment_method": _format_payment_method(pm),
            "status": tx.status,
            "transaction_type": tx.transaction_type,
            "pickup_address": pickup_address,
            "destination_address": destination_address,
            "created_at": tx.created_at,
            "booking_ref": booking_ref,
        }
