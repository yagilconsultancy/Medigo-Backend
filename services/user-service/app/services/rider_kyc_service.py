import logging

from uuid import UUID

from app.repositories.admin_rider_repo import AdminRiderRepository
from app.schemas.admin_rider import SubmitRiderKYCRequest
from mediride_common.exceptions import ValidationError
from mediride_common.schemas.enums import KYCStatus
from mediride_common.utils import utc_now

logger = logging.getLogger(__name__)


class RiderKYCService:
    """Rider-initiated identity verification.

    Separate from AdminRiderService: this is the rider acting on their own
    record, and it only needs the KYC repository rather than the full set of
    cross-service clients the admin views require.
    """

    def __init__(self, repo: AdminRiderRepository):
        self.repo = repo

    async def get_status(self, rider_id: UUID):
        return await self.repo.get_kyc(rider_id)

    async def submit(self, rider_id: UUID, request: SubmitRiderKYCRequest):
        """Submit identity details for admin review.

        Resubmitting after a rejection clears the previous decision and puts the
        record back in the queue. An already-verified rider is blocked so a
        resubmission cannot quietly downgrade a passed check.
        """
        existing = await self.repo.get_kyc(rider_id)
        if existing and existing.kyc_status == KYCStatus.VERIFIED:
            raise ValidationError("Your identity has already been verified")

        record = await self.repo.upsert_kyc(
            rider_id,
            **request.model_dump(),
            kyc_status=KYCStatus.SUBMITTED,
            submitted_at=utc_now(),
            rejection_reason=None,
            verified_at=None,
            verified_by=None,
        )
        logger.info(f"Rider {rider_id} submitted KYC for review")
        return record
