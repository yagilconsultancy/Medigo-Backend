import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from app.clients.stripe_client import StripeClient
from app.clients.user_service_client import UserServiceClient
from app.repositories.admin_payout_repo import AdminPayoutRepository
from app.repositories.earnings_repo import EarningsRepository
from app.repositories.payment_method_repo import PaymentMethodRepository
from app.repositories.transaction_repo import TransactionRepository
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher

logger = logging.getLogger(__name__)


class AdminPayoutService:
    def __init__(
        self,
        payout_repo: AdminPayoutRepository,
        earnings_repo: EarningsRepository,
        pm_repo: PaymentMethodRepository,
        tx_repo: TransactionRepository,
        stripe_client: StripeClient,
        user_client: UserServiceClient,
        publisher: EventPublisher,
    ):
        self.payout_repo = payout_repo
        self.earnings_repo = earnings_repo
        self.pm_repo = pm_repo
        self.tx_repo = tx_repo
        self.stripe = stripe_client
        self.user_client = user_client
        self.publisher = publisher

    async def _get_caregiver_driver_ids(self) -> list[UUID]:
        """Fetch driver IDs who have a specialty (caregivers) from user-service."""
        # Get all drivers with earnings, then filter by specialty via user-service
        # This is called when is_caregiver=True
        return []  # Populated by caller via user enrichment

    async def get_payout_kpis(self, is_caregiver: bool = False, caregiver_ids: list | None = None) -> dict:
        driver_ids = caregiver_ids if is_caregiver and caregiver_ids else None
        return await self.payout_repo.get_payout_kpis(driver_ids=driver_ids)

    async def get_payout_schedule(self) -> list[dict]:
        return await self.payout_repo.get_payout_schedule()

    async def get_earnings_breakdown(self, is_caregiver: bool = False, caregiver_ids: list | None = None) -> dict:
        driver_ids = caregiver_ids if is_caregiver and caregiver_ids else None
        return await self.payout_repo.get_earnings_breakdown_aggregate(driver_ids=driver_ids)

    async def get_monthly_distribution(self) -> list[dict]:
        now = datetime.now(timezone.utc)
        return await self.payout_repo.get_monthly_earnings_distribution(now.year)

    async def get_payouts_by_specialty(self, specialty_driver_map: dict[str, list]) -> list[dict]:
        return await self.payout_repo.get_payouts_by_specialty(specialty_driver_map)

    async def get_driver_earnings_list(
        self,
        search: str | None,
        is_caregiver: bool,
        specialty: str | None,
        page: int,
        limit: int,
    ) -> tuple[list[dict], int]:
        offset = (page - 1) * limit

        # Get base earnings list from repo (may be filtered by caregiver_ids)
        items, total = await self.payout_repo.get_driver_earnings_list(
            offset=offset,
            limit=limit,
        )

        if not items:
            return [], total

        # Enrich with user details
        driver_ids = [item["driver_id"] for item in items]
        driver_details = await self.user_client.get_drivers_with_details(driver_ids)
        detail_map = {d["driver_id"]: d for d in driver_details}

        enriched = []
        for item in items:
            did = str(item["driver_id"])
            details = detail_map.get(did, {})

            driver_name = f"{details.get('first_name', '')} {details.get('last_name', '')}".strip() or "Unknown"
            driver_specialty = details.get("specialty")

            # Filter by caregiver/specialty if requested
            if is_caregiver and not driver_specialty:
                continue
            if specialty and driver_specialty != specialty:
                continue
            if search:
                search_lower = search.lower()
                searchable = f"{driver_name} {details.get('fleet_name', '')}".lower()
                if search_lower not in searchable:
                    continue

            item["driver_name"] = driver_name
            item["avatar_url"] = details.get("avatar_url")
            item["fleet_name"] = details.get("fleet_name")
            item["specialty"] = driver_specialty
            enriched.append(item)

        return enriched, len(enriched)

    async def get_payout_detail(self, driver_id: UUID) -> dict:
        balance = await self.earnings_repo.get_balance(driver_id)
        if not balance:
            return {}

        # Get user details
        user_profile = await self.user_client.get_user_profile(driver_id)
        name = "Unknown"
        if user_profile:
            name = f"{user_profile.get('first_name', '')} {user_profile.get('last_name', '')}".strip() or "Unknown"

        gross = float(balance.total_earned)
        commission = round(gross * 0.20, 2)
        net = float(balance.available_balance)

        # Get trip count
        from sqlalchemy import func as sa_func, select
        from app.models.fare_breakdown import FareBreakdown

        # Get default payment method
        pm = await self.pm_repo.get_default(driver_id)
        bank_last_four = pm.last_four if pm else None

        return {
            "driver_id": driver_id,
            "driver_name": name,
            "net_payout": net,
            "trips": balance.total_earned and int(gross / 15) or 0,  # Approximate
            "gross_earned": gross,
            "commission": commission,
            "commission_percent": 20.0,
            "payout_schedule": "Weekly / Every Monday",
            "payout_method": "Direct Deposit",
            "bank_last_four": bank_last_four,
        }

    async def process_payout(self, driver_id: UUID, admin_id: UUID) -> dict:
        balance = await self.earnings_repo.get_balance(driver_id)
        if not balance or float(balance.available_balance) <= 0:
            raise ValueError("No available balance for payout")

        amount = float(balance.available_balance)

        # Get payment method
        pm = await self.pm_repo.get_default(driver_id)
        if not pm or not pm.external_id:
            raise ValueError("Driver has no valid payment method for payout")

        # Deduct from available balance
        await self.earnings_repo.deduct_for_withdrawal(driver_id, amount)

        # Process via Stripe
        try:
            result = await self.stripe.process_payout(
                order_id=f"PAYOUT-{driver_id}",
                amount=amount,
                data_key=pm.external_id,
                connected_account_id=pm.stripe_customer_id or "",
            )

            if result.success:
                await self.earnings_repo.complete_withdrawal(driver_id, amount)

                await self.publisher.publish(
                    Exchanges.PAYMENTS,
                    RoutingKeys.PAYOUT_COMPLETED,
                    {
                        "driver_id": str(driver_id),
                        "amount": amount,
                        "status": "completed",
                    },
                )

                return {"status": "completed", "amount": amount}
            else:
                # Reverse deduction on failure
                await self.earnings_repo.reverse_withdrawal_deduction(driver_id, amount)

                await self.publisher.publish(
                    Exchanges.PAYMENTS,
                    RoutingKeys.PAYOUT_FAILED,
                    {
                        "driver_id": str(driver_id),
                        "amount": amount,
                        "reason": result.message,
                    },
                )

                raise ValueError(f"Stripe payout failed: {result.message}")

        except Exception as e:
            # Reverse deduction on any error
            await self.earnings_repo.reverse_withdrawal_deduction(driver_id, amount)
            logger.error(f"Payout failed for driver {driver_id}: {e}")
            raise
