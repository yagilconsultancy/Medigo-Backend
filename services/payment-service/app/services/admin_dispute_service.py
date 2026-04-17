import logging
import uuid
from datetime import datetime, timezone
from uuid import UUID

from app.models.dispute import Dispute, DisputeNote
from app.models.refund_request import RefundRequest
from app.repositories.dispute_repo import DisputeNoteRepository, DisputeRepository
from app.repositories.refund_request_repo import RefundRequestRepository
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher

logger = logging.getLogger(__name__)


class AdminDisputeService:
    def __init__(
        self,
        dispute_repo: DisputeRepository,
        note_repo: DisputeNoteRepository,
        refund_repo: RefundRequestRepository,
        publisher: EventPublisher,
    ):
        self.dispute_repo = dispute_repo
        self.note_repo = note_repo
        self.refund_repo = refund_repo
        self.publisher = publisher

    async def get_dispute_kpis(self) -> dict:
        return await self.dispute_repo.get_kpis()

    async def get_disputes(
        self,
        status_filter: str | None,
        dispute_type_filter: str | None,
        search: str | None,
        page: int,
        limit: int,
    ) -> tuple[list[Dispute], int]:
        offset = (page - 1) * limit
        disputes, total = await self.dispute_repo.get_all(
            status_filter=status_filter,
            dispute_type_filter=dispute_type_filter,
            search=search,
            offset=offset,
            limit=limit,
        )
        return disputes, total

    async def get_dispute_detail(self, dispute_id: UUID) -> Dispute | None:
        return await self.dispute_repo.get_by_id(dispute_id)

    async def create_dispute(self, data: dict) -> Dispute:
        dispute = Dispute(
            id=uuid.uuid4(),
            dispute_type=data["dispute_type"],
            status="under_review",
            ride_id=data["ride_id"],
            rider_id=data["rider_id"],
            rider_name=data["rider_name"],
            driver_id=data.get("driver_id"),
            driver_name=data.get("driver_name"),
            trip_code=data["trip_code"],
            billed_amount=data["billed_amount"],
            claimed_amount=data["claimed_amount"],
            reason=data["reason"],
        )

        dispute = await self.dispute_repo.create(dispute)

        await self.publisher.publish(
            Exchanges.PAYMENTS,
            RoutingKeys.DISPUTE_CREATED,
            {
                "dispute_id": str(dispute.id),
                "dispute_number": dispute.dispute_number,
                "dispute_type": dispute.dispute_type,
                "ride_id": str(dispute.ride_id),
                "rider_id": str(dispute.rider_id),
                "billed_amount": float(dispute.billed_amount),
                "claimed_amount": float(dispute.claimed_amount),
                "status": "under_review",
            },
        )

        return dispute

    async def approve_dispute(
        self,
        dispute_id: UUID,
        admin_id: UUID,
        admin_name: str,
        decision_note: str,
        create_refund: bool = False,
        refund_amount: float | None = None,
    ) -> Dispute:
        dispute = await self.dispute_repo.get_by_id(dispute_id)
        if not dispute:
            raise ValueError("Dispute not found")
        if dispute.status != "under_review":
            raise ValueError(f"Dispute is already {dispute.status}")

        now = datetime.now(timezone.utc)

        # Create refund request if requested
        refund_request_id = None
        if create_refund:
            amount = refund_amount if refund_amount else float(dispute.claimed_amount)
            refund = RefundRequest(
                ride_id=dispute.ride_id,
                rider_id=dispute.rider_id,
                driver_id=dispute.driver_id,
                amount=amount,
                category="overcharged",
                reason=f"Approved dispute DIS-{dispute.dispute_number}: {dispute.reason}",
                status="pending",
            )
            refund = await self.refund_repo.create(refund)
            refund_request_id = refund.id

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
                    "from_dispute_id": str(dispute.id),
                },
            )

        # Update dispute
        await self.dispute_repo.update(
            dispute_id,
            status="approved",
            reviewed_by=admin_id,
            reviewed_at=now,
            decision_note=decision_note,
            refund_request_id=refund_request_id,
        )

        await self.publisher.publish(
            Exchanges.PAYMENTS,
            RoutingKeys.DISPUTE_APPROVED,
            {
                "dispute_id": str(dispute_id),
                "dispute_number": dispute.dispute_number,
                "ride_id": str(dispute.ride_id),
                "rider_id": str(dispute.rider_id),
                "status": "approved",
                "refund_request_id": str(refund_request_id) if refund_request_id else None,
            },
        )

        return await self.dispute_repo.get_by_id(dispute_id)

    async def reject_dispute(
        self,
        dispute_id: UUID,
        admin_id: UUID,
        admin_name: str,
        decision_note: str,
    ) -> Dispute:
        dispute = await self.dispute_repo.get_by_id(dispute_id)
        if not dispute:
            raise ValueError("Dispute not found")
        if dispute.status != "under_review":
            raise ValueError(f"Dispute is already {dispute.status}")

        now = datetime.now(timezone.utc)
        await self.dispute_repo.update(
            dispute_id,
            status="rejected",
            reviewed_by=admin_id,
            reviewed_at=now,
            decision_note=decision_note,
        )

        await self.publisher.publish(
            Exchanges.PAYMENTS,
            RoutingKeys.DISPUTE_REJECTED,
            {
                "dispute_id": str(dispute_id),
                "dispute_number": dispute.dispute_number,
                "ride_id": str(dispute.ride_id),
                "rider_id": str(dispute.rider_id),
                "status": "rejected",
            },
        )

        return await self.dispute_repo.get_by_id(dispute_id)

    # ── Notes ──

    async def add_note(
        self,
        dispute_id: UUID,
        admin_id: UUID,
        admin_name: str,
        note_text: str,
    ) -> DisputeNote:
        # Verify dispute exists
        dispute = await self.dispute_repo.get_by_id(dispute_id)
        if not dispute:
            raise ValueError("Dispute not found")

        note = DisputeNote(
            id=uuid.uuid4(),
            dispute_id=dispute_id,
            admin_id=admin_id,
            admin_name=admin_name,
            note=note_text,
        )
        return await self.note_repo.create(note)

    async def delete_note(self, note_id: UUID) -> bool:
        return await self.note_repo.delete(note_id)
