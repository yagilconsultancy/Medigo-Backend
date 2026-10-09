"""Driver activation: the email gate on the mobile Driver tab."""
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.auth_service import AuthService
from mediride_common.exceptions import ConflictError, ValidationError
from mediride_common.schemas.enums import UserRole


def _credential(*, verified=False, role=UserRole.DRIVER, active=True):
    cred = MagicMock()
    cred.id = uuid4()
    cred.email = "driver@example.com"
    cred.phone = None
    cred.role = role
    cred.is_active = active
    cred.is_verified = verified
    cred.business_id = uuid4()
    return cred


def _service(credential, profile, monkeypatch=None):
    credential_repo = MagicMock()
    credential_repo.get_by_email_or_phone = AsyncMock(return_value=credential)
    credential_repo.update_password = AsyncMock()
    credential_repo.update_verified = AsyncMock()
    credential_repo.session = MagicMock()

    token_repo = MagicMock()
    token_repo.create = AsyncMock()

    otp_service = MagicMock()
    otp_service.generate_otp = AsyncMock(return_value="123456")
    otp_service.verify_otp = AsyncMock(return_value=True)

    token_pair = MagicMock()
    token_pair.refresh_token = "refresh-token"
    jwt_handler = MagicMock()
    jwt_handler.create_token_pair = MagicMock(return_value=token_pair)

    publisher = MagicMock()
    publisher.publish = AsyncMock()

    client = MagicMock()
    client.get_driver_profile = AsyncMock(return_value=profile)

    svc = AuthService(
        credential_repo=credential_repo,
        token_repo=token_repo,
        otp_service=otp_service,
        jwt_handler=jwt_handler,
        publisher=publisher,
        user_service_client=client,
    )
    svc._validate_password = AsyncMock()
    return svc, token_pair


APPROVED = {"is_approved": True, "account_status": "active"}


@pytest.mark.asyncio
async def test_unknown_email_is_not_activated():
    svc, _ = _service(None, None)
    result = await svc.check_driver_activation("nobody@example.com")
    assert result["next_step"] == "not_activated"
    assert "admin@getmedigo.com" in result["message"]


@pytest.mark.asyncio
async def test_rider_email_is_not_activated():
    svc, _ = _service(_credential(role=UserRole.RIDER), APPROVED)
    assert (await svc.check_driver_activation("x@example.com"))["next_step"] == "not_activated"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "profile",
    [
        None,
        {"is_approved": False, "account_status": "active"},
        {"is_approved": True, "account_status": "suspended"},
    ],
)
async def test_unapproved_driver_is_not_activated(profile):
    svc, _ = _service(_credential(), profile)
    assert (await svc.check_driver_activation("d@example.com"))["next_step"] == "not_activated"


@pytest.mark.asyncio
async def test_inactive_credential_is_not_activated():
    svc, _ = _service(_credential(active=False), APPROVED)
    assert (await svc.check_driver_activation("d@example.com"))["next_step"] == "not_activated"


@pytest.mark.asyncio
async def test_approved_without_password_needs_set_password():
    svc, _ = _service(_credential(verified=False), APPROVED)
    result = await svc.check_driver_activation("d@example.com")
    assert result["next_step"] == "set_password"
    assert result["message"] is None


@pytest.mark.asyncio
async def test_approved_with_password_goes_to_login():
    svc, _ = _service(_credential(verified=True), APPROVED)
    assert (await svc.check_driver_activation("d@example.com"))["next_step"] == "login"


@pytest.mark.asyncio
async def test_otp_sent_only_when_set_password():
    cred = _credential(verified=False)
    svc, _ = _service(cred, APPROVED)
    await svc.request_driver_activation_otp("d@example.com")
    svc.otp_service.generate_otp.assert_awaited_once_with(
        cred.id, "driver_activation", "email", expire_minutes=7 * 24 * 60
    )
    svc.publisher.publish.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("cred,profile", [
    (None, None),
    (_credential(verified=True), APPROVED),
    (_credential(verified=False), {"is_approved": False, "account_status": "active"}),
])
async def test_no_otp_for_other_states(cred, profile):
    svc, _ = _service(cred, profile)
    await svc.request_driver_activation_otp("d@example.com")
    svc.otp_service.generate_otp.assert_not_awaited()
    svc.publisher.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_sets_password_and_verifies_without_logging_in(monkeypatch):
    monkeypatch.setattr("app.services.auth_service.hash_password", lambda p: f"hashed-{p}")
    cred = _credential(verified=False)
    svc, _ = _service(cred, APPROVED)
    result = await svc.complete_driver_activation("d@example.com", "123456", "NewPassword1!")
    assert result is None  # driver is sent to the login page, not logged in
    svc.otp_service.verify_otp.assert_awaited_once_with(cred.id, "123456", "driver_activation")
    svc.credential_repo.update_password.assert_awaited_once_with(cred.id, "hashed-NewPassword1!")
    svc.credential_repo.update_verified.assert_awaited_once_with(cred.id, True)
    svc.jwt_handler.create_token_pair.assert_not_called()
    svc.token_repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_internal_send_code_for_approved_new_driver():
    cred = _credential(verified=False)
    svc, _ = _service(cred, APPROVED)
    svc.credential_repo.get_by_id = AsyncMock(return_value=cred)
    assert await svc.send_driver_activation_code(cred.id) is True
    svc.publisher.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_internal_send_code_skipped_when_already_activated():
    cred = _credential(verified=True)
    svc, _ = _service(cred, APPROVED)
    svc.credential_repo.get_by_id = AsyncMock(return_value=cred)
    assert await svc.send_driver_activation_code(cred.id) is False
    svc.publisher.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_bad_otp_changes_nothing():
    cred = _credential(verified=False)
    svc, _ = _service(cred, APPROVED)
    svc.otp_service.verify_otp = AsyncMock(side_effect=ValidationError("Invalid OTP code"))
    with pytest.raises(ValidationError):
        await svc.complete_driver_activation("d@example.com", "000000", "NewPassword1!")
    svc.credential_repo.update_password.assert_not_awaited()
    svc.credential_repo.update_verified.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_refused_when_not_activated():
    svc, _ = _service(_credential(), {"is_approved": False, "account_status": "active"})
    with pytest.raises(ValidationError):
        await svc.complete_driver_activation("d@example.com", "123456", "NewPassword1!")
    svc.otp_service.verify_otp.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_refused_when_password_already_set():
    """A leaked/guessed code must not let someone overwrite an existing password."""
    svc, _ = _service(_credential(verified=True), APPROVED)
    with pytest.raises(ConflictError):
        await svc.complete_driver_activation("d@example.com", "123456", "NewPassword1!")
    svc.credential_repo.update_password.assert_not_awaited()
