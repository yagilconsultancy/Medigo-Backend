from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services import otp_service as otp_module


@pytest.mark.asyncio
async def test_generate_otp_uses_dynamic_generator(monkeypatch):
    otp_repo = SimpleNamespace(
        count_recent_for_user=AsyncMock(return_value=0),
        create=AsyncMock(),
    )
    monkeypatch.setattr(otp_module, "generate_otp", lambda: "482913")

    service = otp_module.OTPService(otp_repo)
    code = await service.generate_otp(uuid4(), "registration", "email")

    assert code == "482913"
    created_otp = otp_repo.create.await_args.args[0]
    # Stored as a hash, never the plain code.
    assert created_otp.code != "482913"
    assert created_otp.code.startswith("h1:")


def _otp_record(code="111111", attempts=0):
    return SimpleNamespace(id=uuid4(), code=code, attempts=attempts)


@pytest.mark.asyncio
async def test_wrong_code_persists_attempt_before_raising():
    """A wrong guess must commit the attempt counter, because the raised error
    makes get_db() roll the request back (which previously allowed unlimited
    guesses)."""
    from mediride_common.exceptions import ValidationError

    session = SimpleNamespace(commit=AsyncMock())
    otp_repo = SimpleNamespace(
        session=session,
        get_latest_unverified=AsyncMock(return_value=_otp_record()),
        increment_attempts=AsyncMock(),
        mark_verified=AsyncMock(),
    )
    service = otp_module.OTPService(otp_repo)

    with pytest.raises(ValidationError):
        await service.verify_otp(uuid4(), "999999", "password_reset")

    otp_repo.increment_attempts.assert_awaited_once()
    session.commit.assert_awaited_once()
    otp_repo.mark_verified.assert_not_awaited()


@pytest.mark.asyncio
async def test_wrong_code_still_raises_if_commit_fails():
    from mediride_common.exceptions import ValidationError

    session = SimpleNamespace(commit=AsyncMock(side_effect=RuntimeError("db down")))
    otp_repo = SimpleNamespace(
        session=session,
        get_latest_unverified=AsyncMock(return_value=_otp_record()),
        increment_attempts=AsyncMock(),
        mark_verified=AsyncMock(),
    )
    service = otp_module.OTPService(otp_repo)

    with pytest.raises(ValidationError):
        await service.verify_otp(uuid4(), "999999", "password_reset")


@pytest.mark.asyncio
async def test_code_is_refused_once_attempts_are_used_up():
    from mediride_common.exceptions import ValidationError

    otp_repo = SimpleNamespace(
        session=SimpleNamespace(commit=AsyncMock()),
        get_latest_unverified=AsyncMock(
            return_value=_otp_record(attempts=otp_module.settings.OTP_MAX_ATTEMPTS)
        ),
        increment_attempts=AsyncMock(),
        mark_verified=AsyncMock(),
    )
    service = otp_module.OTPService(otp_repo)

    # Even the correct code is refused after the cap.
    with pytest.raises(ValidationError):
        await service.verify_otp(uuid4(), "111111", "password_reset")
    otp_repo.mark_verified.assert_not_awaited()


@pytest.mark.asyncio
async def test_correct_code_marks_verified_without_early_commit():
    otp_repo = SimpleNamespace(
        session=SimpleNamespace(commit=AsyncMock()),
        get_latest_unverified=AsyncMock(return_value=_otp_record()),
        increment_attempts=AsyncMock(),
        mark_verified=AsyncMock(),
    )
    service = otp_module.OTPService(otp_repo)

    assert await service.verify_otp(uuid4(), "111111", "password_reset") is True
    otp_repo.mark_verified.assert_awaited_once()
    otp_repo.session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_hashed_code_verifies_and_wrong_code_fails():
    from mediride_common.exceptions import ValidationError

    user_id = uuid4()
    stored = otp_module.hash_otp(user_id, "registration", "482913")
    session = SimpleNamespace(commit=AsyncMock())
    otp_repo = SimpleNamespace(
        session=session,
        get_latest_unverified=AsyncMock(return_value=_otp_record(code=stored)),
        increment_attempts=AsyncMock(),
        mark_verified=AsyncMock(),
    )
    service = otp_module.OTPService(otp_repo)

    assert await service.verify_otp(user_id, "482913", "registration") is True
    otp_repo.mark_verified.assert_awaited_once()

    with pytest.raises(ValidationError):
        await service.verify_otp(user_id, "000000", "registration")


@pytest.mark.asyncio
async def test_hashed_code_is_bound_to_user_and_purpose():
    from mediride_common.exceptions import ValidationError

    stored = otp_module.hash_otp(uuid4(), "registration", "482913")
    otp_repo = SimpleNamespace(
        session=SimpleNamespace(commit=AsyncMock()),
        get_latest_unverified=AsyncMock(return_value=_otp_record(code=stored)),
        increment_attempts=AsyncMock(),
        mark_verified=AsyncMock(),
    )
    service = otp_module.OTPService(otp_repo)

    # Same digits, different user: must not match.
    with pytest.raises(ValidationError):
        await service.verify_otp(uuid4(), "482913", "registration")


@pytest.mark.asyncio
async def test_legacy_plain_code_still_accepted_until_it_expires():
    otp_repo = SimpleNamespace(
        session=SimpleNamespace(commit=AsyncMock()),
        get_latest_unverified=AsyncMock(return_value=_otp_record(code="111111")),
        increment_attempts=AsyncMock(),
        mark_verified=AsyncMock(),
    )
    service = otp_module.OTPService(otp_repo)

    assert await service.verify_otp(uuid4(), "111111", "password_reset") is True
