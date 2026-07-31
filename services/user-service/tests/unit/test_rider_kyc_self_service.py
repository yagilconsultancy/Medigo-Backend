from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.schemas.admin_rider import SubmitRiderKYCRequest
from app.schemas.document import RIDER_DOCUMENT_TYPES, DocumentType
from app.services.rider_kyc_service import RiderKYCService
from mediride_common.exceptions import ValidationError
from mediride_common.schemas.enums import KYCStatus


def _make_service(existing=None):
    repo = MagicMock()
    repo.get_kyc = AsyncMock(return_value=existing)
    repo.upsert_kyc = AsyncMock(return_value=SimpleNamespace())
    return RiderKYCService(repo), repo


def _kyc(status):
    return SimpleNamespace(kyc_status=status)


@pytest.mark.asyncio
async def test_first_submission_queues_the_record_for_review():
    service, repo = _make_service(existing=None)
    rider_id = uuid4()

    await service.submit(
        rider_id,
        SubmitRiderKYCRequest(id_type="drivers_license", id_number="D999"),
    )

    kwargs = repo.upsert_kyc.await_args.kwargs
    assert kwargs["kyc_status"] == KYCStatus.SUBMITTED
    assert kwargs["submitted_at"] is not None
    assert kwargs["id_number"] == "D999"


@pytest.mark.asyncio
async def test_resubmitting_after_rejection_clears_the_previous_decision():
    """Otherwise a rider would keep seeing a stale rejection reason."""
    service, repo = _make_service(existing=_kyc(KYCStatus.REJECTED))

    await service.submit(
        uuid4(), SubmitRiderKYCRequest(id_type="passport", id_number="P1")
    )

    kwargs = repo.upsert_kyc.await_args.kwargs
    assert kwargs["kyc_status"] == KYCStatus.SUBMITTED
    assert kwargs["rejection_reason"] is None
    assert kwargs["verified_at"] is None
    assert kwargs["verified_by"] is None


@pytest.mark.asyncio
async def test_a_verified_rider_cannot_resubmit():
    """A resubmission must not quietly downgrade a passed check."""
    service, repo = _make_service(existing=_kyc(KYCStatus.VERIFIED))

    with pytest.raises(ValidationError, match="already been verified"):
        await service.submit(
            uuid4(), SubmitRiderKYCRequest(id_type="passport", id_number="P1")
        )
    repo.upsert_kyc.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_status_returns_none_for_a_rider_who_never_submitted():
    service, _ = _make_service(existing=None)
    assert await service.get_status(uuid4()) is None


def test_riders_may_only_upload_identity_documents():
    """Vehicle and transport-certification types are driver-only."""
    allowed = {t.value for t in RIDER_DOCUMENT_TYPES}
    assert DocumentType.GOVERNMENT_ID_FRONT.value in allowed
    assert DocumentType.GOVERNMENT_ID_BACK.value in allowed
    for driver_only in (
        DocumentType.VEHICLE_INSURANCE,
        DocumentType.VEHICLE_REGISTRATION,
        DocumentType.MEDICAL_TRANSPORT_CERTIFICATION,
    ):
        assert driver_only.value not in allowed
