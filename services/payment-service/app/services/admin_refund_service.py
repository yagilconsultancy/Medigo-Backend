import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from app.clients.stripe_client import StripeClient
from app.clients.user_service_client import UserServiceClient
from app.models.refund_request import RefundRequest
from app.models.transaction import Transaction
from app.repositories.refund_request_repo import RefundRequestRepository
from app.repositories.transaction_repo import TransactionRepository
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher

logger = logging.getLogger(__name__)


class AdminRefundService:
    def __init__(
        self,
        refund_repo: RefundRequestRepository,
        tx_repo: TransactionRepository,
        stripe_client: StripeClient,
        user_client: UserServiceClient,
        publisher: EventPublisher,
    ):
        self.refund_repo = refund_repo
        self.tx_repo = tx_repo
        self.stripe = stripe_client
        self.user_client = user_client
        self.publisher = publisher

    async def get_refund_kpis(self) -> dict:
        return await self.refund_repo.get_kpis()

    async def get_refund_requests(
        self,
        status_filter: str | None,
        search: str | None,
        page: int,
        limit: int,
    ) -> tuple[list[dict], int]:
        offset = (page - 1) * limit
        refunds, total = await self.refund_repo.get_all(
            status_filter=status_filter,
            search=search,
            offset=offset,
            limit=limit,
        )

        # Collect user IDs for enrichment
        user_ids: set[UUID] = set()
        for r in refunds:
            user_ids.add(r.rider_id)
            if r.driver_id:
                user_ids.add(r.driver_id)

        # Fetch profiles concurrently
        user_map: dict[str, dict] = {}

        async def _fetch(uid: UUID):
            profile = await self.user_client.get_user_profile(uid)
            if profile:
                user_map[str(uid)] = profile

        await asyncio.gather(*[_fetch(uid) for uid in user_ids])

        items = []
        for r in refunds:
            rider = user_map.get(str(r.rider_id), {})
            rider_name = f"{rider.get('first_name', '')} {rider.get('last_name', '')}".strip() or "Unknown"

            driver_name = None
            if r.driver_id:
                driver = user_map.get(str(r.driver_id), {})
                driver_name = f"{driver.get('first_name', '')} {driver.get('last_name', '')}".strip() or None

            items.append({
                "id": r.id,
                "ride_id": r.ride_id,
                "rider_name": rider_name,
                "driver_name": driver_name,
                "category": r.category,
                "amount": float(r.amount),
                "status": r.status,
                "created_at": r.created_at,
            })

        return items, total

    async def get_refund_detail(self, refund_id: UUID) -> dict | None:
        refund = await self.refund_repo.get_by_id(refund_id)
        if not refund:
            return None

        # Enrich with user details
        async def _none():
            return None

        rider_profile, driver_profile = await asyncio.gather(
            self.user_client.get_user_profile(refund.rider_id),
            self.user_client.get_user_profile(refund.driver_id) if refund.driver_id else _none(),
        )

        rider_name = "Unknown"
        rider_phone = None
        if rider_profile:
            rider_name = f"{rider_profile.get('first_name', '')} {rider_profile.get('last_name', '')}".strip() or "Unknown"
            rider_phone = rider_profile.get("phone")

        driver_name = None
        if driver_profile:
            driver_name = f"{driver_profile.get('first_name', '')} {driver_profile.get('last_name', '')}".strip() or None

        return {
            "id": refund.id,
            "ride_id": refund.ride_id,
            "rider_id": refund.rider_id,
            "driver_id": refund.driver_id,
            "rider_name": rider_name,
            "rider_phone": rider_phone,
            "driver_name": driver_name,
            "amount": float(refund.amount),
            "refund_amount": float(refund.refund_amount) if refund.refund_amount else None,
            "is_partial": refund.is_partial,
            "category": refund.category,
            "reason": refund.reason,
            "status": refund.status,
            "decision_note": refund.decision_note,
            "reviewed_by": refund.reviewed_by,
            "reviewed_at": refund.reviewed_at,
            "ride_type": refund.ride_type,
            "payment_method_type": refund.payment_method_type,
            "created_at": refund.created_at,
        }

    async def create_refund_request(self, data: dict) -> RefundRequest:
        # Find the original payment transaction
        transactions, _ = await self.tx_repo.get_by_user(
            user_id=data["rider_id"],
            offset=0,
            limit=100,
            tx_type="ride_payment",
        )
        transaction_id = None
        for tx in transactions:
            if tx.ride_id == data["ride_id"] and tx.status == "completed":
                transaction_id = tx.id
                break

        refund = RefundRequest(
            ride_id=data["ride_id"],
            transaction_id=transaction_id,
            rider_id=data["rider_id"],
            driver_id=data.get("driver_id"),
            amount=data["amount"],
            category=data["category"],
            reason=data.get("reason"),
            ride_type=data.get("ride_type"),
            payment_method_type=data.get("payment_method_type"),
            status="pending",
        )

        refund = await self.refund_repo.create(refund)

        await self.publisher.publish(
            Exchanges.PAYMENTS,
            RoutingKeys.REFUND_REQUEST_CREATED,
            {
                "refund_request_id": str(refund.id),
                "ride_id": str(refund.ride_id),
                "rider_id": str(refund.rider_id),
                "amount": float(refund.amount),
                "category": refund.category,
                "status": "pending",
            },
        )

        return refund

    async def approve_refund(
        self,
        refund_id: UUID,
        admin_id: UUID,
        decision_note: str,
        is_partial: bool = False,
        partial_amount: float | None = None,
    ) -> dict:
        refund = await self.refund_repo.get_by_id(refund_id)
        if not refund:
            raise ValueError("Refund request not found")
        if refund.status != "pending":
            raise ValueError(f"Refund is already {refund.status}")

        refund_amount = partial_amount if is_partial and partial_amount else float(refund.amount)

        # Process Stripe refund if we have a transaction
        stripe_refund_id = None
        refund_tx_id = None

        if refund.transaction_id:
            # Find original transaction for Stripe reference
            original_tx = await self.tx_repo.get_by_id(refund.transaction_id)
            if original_tx and original_tx.reference_id:
                result = await self.stripe.refund(
                    order_id=f"REFUND-{refund.ride_id}",
                    transaction_id=original_tx.reference_id,
                    amount=refund_amount,
                )
                if result.success:
                    stripe_refund_id = result.transaction_id

                    # Create refund transaction record
                    refund_tx = Transaction(
                        ride_id=refund.ride_id,
                        user_id=refund.rider_id,
                        transaction_type="refund",
                        amount=refund_amount,
                        currency="CAD",
                        status="completed",
                        description=f"Refund: {refund.category} - {decision_note[:100]}",
                        reference_id=stripe_refund_id,
                    )
                    refund_tx = await self.tx_repo.create(refund_tx)
                    refund_tx_id = refund_tx.id
                else:
                    raise ValueError(f"Stripe refund failed: {result.message}")

        # Update refund request
        now = datetime.now(timezone.utc)
        await self.refund_repo.update(
            refund_id,
            status="approved",
            refund_amount=refund_amount,
            is_partial=is_partial,
            reviewed_by=admin_id,
            reviewed_at=now,
            decision_note=decision_note,
            stripe_refund_id=stripe_refund_id,
            refund_transaction_id=refund_tx_id,
        )

        await self.publisher.publish(
            Exchanges.PAYMENTS,
            RoutingKeys.REFUND_REQUEST_APPROVED,
            {
                "refund_request_id": str(refund_id),
                "ride_id": str(refund.ride_id),
                "rider_id": str(refund.rider_id),
                "amount": refund_amount,
                "status": "approved",
            },
        )

        return await self.get_refund_detail(refund_id)

    async def reject_refund(
        self,
        refund_id: UUID,
        admin_id: UUID,
        decision_note: str,
    ) -> dict:
        refund = await self.refund_repo.get_by_id(refund_id)
        if not refund:
            raise ValueError("Refund request not found")
        if refund.status != "pending":
            raise ValueError(f"Refund is already {refund.status}")

        now = datetime.now(timezone.utc)
        await self.refund_repo.update(
            refund_id,
            status="rejected",
            reviewed_by=admin_id,
            reviewed_at=now,
            decision_note=decision_note,
        )

        await self.publisher.publish(
            Exchanges.PAYMENTS,
            RoutingKeys.REFUND_REQUEST_REJECTED,
            {
                "refund_request_id": str(refund_id),
                "ride_id": str(refund.ride_id),
                "rider_id": str(refund.rider_id),
                "amount": float(refund.amount),
                "status": "rejected",
            },
        )

        return await self.get_refund_detail(refund_id)
