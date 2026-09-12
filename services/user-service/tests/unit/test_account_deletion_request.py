"""Guards for the public account-deletion flow.

The form behind getmedigo.com/medigo-delete-account is unauthenticated, so the
things worth pinning down are the ones that stop it being abused: it must not
reveal which emails belong to MediGo users, a code must actually be required
before an admin ever sees the request, and only a verified request may be
approved into a real deletion.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.account_deletion_request import AccountDeletionRequest
from app.services.account_deletion_request_service import (
    GENERIC_SUBMIT_MESSAGE,
    AccountDeletionRequestService,
)
from mediride_common.exceptions import ConflictError, ValidationError


def _request(**overrides):
    defaults = dict(
        id=uuid4(),
        full_name="Jane Doe",
        email="jane@example.com",
        phone="+14165550123",
        reason=None,
        user_id=uuid4(),
        status=AccountDeletionRequest.STATUS_PENDING_VERIFICATION,
        otp_code_hash=None,
        otp_expires_at=None,
        otp_attempts=0,
        otp_sent_count=0,
        otp_last_sent_at=None,
        email_verified_at=None,
        reviewed_by=None,
        reviewed_at=None,
        rejection_reason=None,
        admin_notes=None,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _service(
    *,
    user=None,
    existing=None,
    recent_count=0,
    created=None,
    user_service=None,
):
    request_repo = MagicMock()
    request_repo.session = MagicMock(flush=AsyncMock())
    request_repo.count_recent_for_email = AsyncMock(return_value=recent_count)
    request_repo.get_active_by_email = AsyncMock(return_value=existing)
    request_repo.create = AsyncMock(
        side_effect=lambda r: created if created is not None else r
    )
    request_repo.get_by_id = AsyncMock(return_value=existing)

    user_repo = MagicMock()
    user_repo.get_by_email_ci = AsyncMock(return_value=user)

    publisher = MagicMock()
    publisher.publish = AsyncMock()

    service = AccountDeletionRequestService(
        request_repo=request_repo,
        user_repo=user_repo,
        user_service=user_service or MagicMock(delete_account=AsyncMock()),
        publisher=publisher,
        settings=SimpleNamespace(JWT_SECRET_KEY="test-secret"),
    )
    return service, request_repo, publisher


# --- Enumeration resistance ---


@pytest.mark.asyncio
async def test_unknown_email_returns_same_message_and_writes_nothing():
    """An address with no account must be indistinguishable from one that has."""
    service, request_repo, publisher = _service(user=None)

    message = await service.submit_request(
        full_name="Jane Doe", email="nobody@example.com", phone=None, reason=None
    )

    assert message == GENERIC_SUBMIT_MESSAGE
    request_repo.create.assert_not_awaited()
    publisher.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_known_email_returns_identical_message():
    service, request_repo, publisher = _service(user=SimpleNamespace(id=uuid4()))

    message = await service.submit_request(
        full_name="Jane Doe", email="jane@example.com", phone=None, reason=None
    )

    assert message == GENERIC_SUBMIT_MESSAGE
    request_repo.create.assert_awaited_once()
    publisher.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_email_is_normalised_before_lookup():
    """A hand-typed 'Jane@Example.COM' must still find the stored account."""
    user = SimpleNamespace(id=uuid4())
    service, request_repo, _ = _service(user=user)

    await service.submit_request(
        full_name="Jane Doe", email="  Jane@Example.COM ", phone=None, reason=None
    )

    service.user_repo.get_by_email_ci.assert_awaited_once_with("jane@example.com")
    assert request_repo.create.await_args.args[0].email == "jane@example.com"


# --- Abuse guards ---


@pytest.mark.asyncio
async def test_daily_cap_suppresses_further_codes():
    service, request_repo, publisher = _service(
        user=SimpleNamespace(id=uuid4()),
        recent_count=AccountDeletionRequestService.MAX_REQUESTS_PER_EMAIL_PER_DAY,
    )

    message = await service.submit_request(
        full_name="Jane Doe", email="jane@example.com", phone=None, reason=None
    )

    assert message == GENERIC_SUBMIT_MESSAGE
    publisher.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_resend_respects_cooldown():
    existing = _request(
        otp_sent_count=1, otp_last_sent_at=datetime.now(timezone.utc)
    )
    service, _, publisher = _service(existing=existing)

    await service.resend_code("jane@example.com")

    publisher.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_resend_allowed_once_cooldown_elapsed():
    existing = _request(
        otp_sent_count=1,
        otp_last_sent_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    service, _, publisher = _service(existing=existing)

    await service.resend_code("jane@example.com")

    publisher.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_resubmitting_does_not_duplicate_a_queued_request():
    """A request already awaiting review must not be reopened or re-coded."""
    existing = _request(status=AccountDeletionRequest.STATUS_PENDING_REVIEW)
    service, request_repo, publisher = _service(
        user=SimpleNamespace(id=uuid4()), existing=existing
    )

    await service.submit_request(
        full_name="Jane Doe", email="jane@example.com", phone=None, reason=None
    )

    request_repo.create.assert_not_awaited()
    publisher.publish.assert_not_awaited()
    assert existing.status == AccountDeletionRequest.STATUS_PENDING_REVIEW


# --- Verification ---


@pytest.mark.asyncio
async def test_correct_code_moves_request_to_review():
    existing = _request()
    service, _, publisher = _service(existing=existing)
    code = service._issue_code(existing)

    result = await service.verify_code("jane@example.com", code)

    assert result.status == AccountDeletionRequest.STATUS_PENDING_REVIEW
    assert result.email_verified_at is not None
    # The code is cleared once spent.
    assert result.otp_code_hash is None
    publisher.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_wrong_code_is_rejected_and_counted():
    existing = _request()
    service, _, _ = _service(existing=existing)
    service._issue_code(existing)

    with pytest.raises(ValidationError):
        await service.verify_code("jane@example.com", "000000")

    assert existing.otp_attempts == 1
    assert existing.status == AccountDeletionRequest.STATUS_PENDING_VERIFICATION


@pytest.mark.asyncio
async def test_expired_code_is_rejected():
    existing = _request()
    service, _, _ = _service(existing=existing)
    code = service._issue_code(existing)
    existing.otp_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    with pytest.raises(ValidationError):
        await service.verify_code("jane@example.com", code)

    assert existing.status == AccountDeletionRequest.STATUS_PENDING_VERIFICATION


@pytest.mark.asyncio
async def test_attempt_cap_locks_out_brute_force():
    existing = _request(
        otp_attempts=AccountDeletionRequestService.OTP_MAX_ATTEMPTS
    )
    service, _, _ = _service(existing=existing)
    code = service._issue_code(existing)
    # _issue_code resets the counter; restore the exhausted state.
    existing.otp_attempts = AccountDeletionRequestService.OTP_MAX_ATTEMPTS

    with pytest.raises(ValidationError) as exc:
        await service.verify_code("jane@example.com", code)

    assert "Too many" in exc.value.message


@pytest.mark.asyncio
async def test_verifying_twice_is_idempotent():
    existing = _request(
        status=AccountDeletionRequest.STATUS_PENDING_REVIEW,
        email_verified_at=datetime.now(timezone.utc),
    )
    service, _, publisher = _service(existing=existing)

    result = await service.verify_code("jane@example.com", "123456")

    assert result.status == AccountDeletionRequest.STATUS_PENDING_REVIEW
    publisher.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_code_hash_is_bound_to_its_request():
    """A code lifted from one request must not verify another."""
    service, _, _ = _service()
    a, b = _request(), _request()

    code = service._issue_code(a)

    assert service._hash_code(code, a.id) == a.otp_code_hash
    assert service._hash_code(code, b.id) != a.otp_code_hash


# --- Admin review ---


@pytest.mark.asyncio
async def test_approve_deletes_the_account():
    existing = _request(status=AccountDeletionRequest.STATUS_PENDING_REVIEW)
    user_service = MagicMock(delete_account=AsyncMock())
    service, _, publisher = _service(
        existing=existing, user_service=user_service
    )
    admin_id = uuid4()

    result = await service.approve_request(existing.id, admin_id, notes="ok")

    user_service.delete_account.assert_awaited_once_with(existing.user_id)
    assert result.status == AccountDeletionRequest.STATUS_APPROVED
    assert result.reviewed_by == admin_id
    publisher.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_unverified_request_cannot_be_approved():
    """The whole point of the OTP is that this path is closed."""
    existing = _request(status=AccountDeletionRequest.STATUS_PENDING_VERIFICATION)
    user_service = MagicMock(delete_account=AsyncMock())
    service, _, _ = _service(existing=existing, user_service=user_service)

    with pytest.raises(ConflictError):
        await service.approve_request(existing.id, uuid4())

    user_service.delete_account.assert_not_awaited()


@pytest.mark.asyncio
async def test_already_approved_request_cannot_be_approved_again():
    existing = _request(status=AccountDeletionRequest.STATUS_APPROVED)
    user_service = MagicMock(delete_account=AsyncMock())
    service, _, _ = _service(existing=existing, user_service=user_service)

    with pytest.raises(ConflictError):
        await service.approve_request(existing.id, uuid4())

    user_service.delete_account.assert_not_awaited()


@pytest.mark.asyncio
async def test_reject_records_reason_and_leaves_account_alone():
    existing = _request(status=AccountDeletionRequest.STATUS_PENDING_REVIEW)
    user_service = MagicMock(delete_account=AsyncMock())
    service, _, publisher = _service(existing=existing, user_service=user_service)

    result = await service.reject_request(existing.id, uuid4(), reason="Open balance")

    assert result.status == AccountDeletionRequest.STATUS_REJECTED
    assert result.rejection_reason == "Open balance"
    user_service.delete_account.assert_not_awaited()
    publisher.publish.assert_awaited_once()
