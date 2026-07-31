from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.schemas.admin_rider import RejectRiderKYCRequest, UpdateRiderRequest
from app.services.admin_rider_service import AdminRiderService
from mediride_common.schemas.enums import KYCStatus


def _make_service(kyc_record=None, rider_exists=True):
    rider_id = uuid4()

    repo = MagicMock()
    repo.get_rider_detail = AsyncMock(
        return_value={"user_id": rider_id, "status": "active"}
        if rider_exists
        else None
    )
    repo.update_user = AsyncMock()
    repo.upsert_kyc = AsyncMock()
    repo.get_kyc = AsyncMock(return_value=kyc_record)

    service = AdminRiderService.__new__(AdminRiderService)
    service.repo = repo
    # Building the full detail response needs cross-service clients; the
    # workflow itself is what's under test.
    service.get_rider_detail = AsyncMock(return_value=MagicMock())

    return service, repo, rider_id


def _kyc(status):
    return SimpleNamespace(kyc_status=status)


@pytest.mark.asyncio
async def test_update_rider_splits_user_and_kyc_fields():
    """Address/insurance go to users; identity fields go to rider_kyc."""
    service, repo, rider_id = _make_service()

    await service.update_rider(
        rider_id,
        UpdateRiderRequest(
            city="Toronto",
            insurance_member_id="MEM-1",
            id_type="passport",
            id_number="X1234567",
        ),
        uuid4(),
    )

    user_kwargs = repo.update_user.await_args.kwargs
    kyc_kwargs = repo.upsert_kyc.await_args.kwargs
    assert user_kwargs == {"city": "Toronto", "insurance_member_id": "MEM-1"}
    assert kyc_kwargs == {"id_type": "passport", "id_number": "X1234567"}


@pytest.mark.asyncio
async def test_update_rider_touches_nothing_for_an_empty_payload():
    service, repo, rider_id = _make_service()

    await service.update_rider(rider_id, UpdateRiderRequest(), uuid4())

    repo.update_user.assert_not_awaited()
    repo.upsert_kyc.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_rider_rejects_an_unknown_rider():
    service, _, rider_id = _make_service(rider_exists=False)

    with pytest.raises(ValueError, match="Rider not found"):
        await service.update_rider(rider_id, UpdateRiderRequest(city="X"), uuid4())


@pytest.mark.asyncio
async def test_approving_kyc_records_the_verifier():
    admin_id = uuid4()
    service, repo, rider_id = _make_service(kyc_record=_kyc(KYCStatus.SUBMITTED))

    await service.approve_rider_kyc(rider_id, admin_id)

    kwargs = repo.upsert_kyc.await_args.kwargs
    assert kwargs["kyc_status"] == KYCStatus.VERIFIED
    assert kwargs["verified_by"] == admin_id
    assert kwargs["verified_at"] is not None
    assert kwargs["rejection_reason"] is None


@pytest.mark.asyncio
async def test_cannot_approve_kyc_that_was_never_submitted():
    service, repo, rider_id = _make_service(kyc_record=None)

    with pytest.raises(ValueError, match="has not submitted"):
        await service.approve_rider_kyc(rider_id, uuid4())
    repo.upsert_kyc.assert_not_awaited()


@pytest.mark.asyncio
async def test_cannot_approve_kyc_twice():
    service, repo, rider_id = _make_service(kyc_record=_kyc(KYCStatus.VERIFIED))

    with pytest.raises(ValueError, match="already verified"):
        await service.approve_rider_kyc(rider_id, uuid4())
    repo.upsert_kyc.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejecting_kyc_stores_the_reason_and_clears_verification():
    service, repo, rider_id = _make_service(kyc_record=_kyc(KYCStatus.SUBMITTED))

    await service.reject_rider_kyc(rider_id, uuid4(), "ID photo unreadable")

    kwargs = repo.upsert_kyc.await_args.kwargs
    assert kwargs["kyc_status"] == KYCStatus.REJECTED
    assert kwargs["rejection_reason"] == "ID photo unreadable"
    assert kwargs["verified_at"] is None


@pytest.mark.asyncio
async def test_cannot_reject_kyc_that_was_never_submitted():
    service, repo, rider_id = _make_service(kyc_record=_kyc(KYCStatus.NOT_STARTED))

    with pytest.raises(ValueError, match="has not submitted"):
        await service.reject_rider_kyc(rider_id, uuid4(), "no")
    repo.upsert_kyc.assert_not_awaited()


def test_reject_request_requires_a_reason():
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        RejectRiderKYCRequest(rejection_reason="")
