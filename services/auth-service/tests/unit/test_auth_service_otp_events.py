import os
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

os.environ["DEBUG"] = "false"
os.environ["ENVIRONMENT"] = "development"


class _DummyPasswordHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password_hash: str, password: str) -> bool:
        return password_hash == f"hashed:{password}"


class _DummyVerifyMismatchError(Exception):
    pass


sys.modules.setdefault("argon2", types.SimpleNamespace(PasswordHasher=_DummyPasswordHasher))
sys.modules.setdefault(
    "argon2.exceptions",
    types.SimpleNamespace(VerifyMismatchError=_DummyVerifyMismatchError),
)
sys.modules.setdefault(
    "aio_pika",
    types.SimpleNamespace(
        connect_robust=None,
        ExchangeType=types.SimpleNamespace(TOPIC="topic", FANOUT="fanout"),
        Message=object,
        DeliveryMode=types.SimpleNamespace(PERSISTENT=2),
    ),
)
sys.modules.setdefault(
    "aio_pika.abc",
    types.SimpleNamespace(
        AbstractChannel=object,
        AbstractConnection=object,
        AbstractExchange=object,
        AbstractIncomingMessage=object,
    ),
)

from app.services.auth_service import AuthService
from mediride_common.exceptions import AuthenticationError, ConflictError
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.schemas.enums import UserRole


@pytest.mark.asyncio
async def test_register_publishes_otp_requested_event():
    user_id = uuid4()
    credential_repo = MagicMock()
    credential_repo.get_by_email_or_phone = AsyncMock(return_value=None)
    credential_repo.create = AsyncMock()
    token_repo = MagicMock()
    otp_service = MagicMock()
    otp_service.generate_otp = AsyncMock(return_value="482913")
    publisher = MagicMock()
    publisher.publish = AsyncMock()

    service = AuthService(
        credential_repo=credential_repo,
        token_repo=token_repo,
        otp_service=otp_service,
        jwt_handler=MagicMock(),
        publisher=publisher,
    )

    async def create_side_effect(credential):
        credential.id = user_id

    credential_repo.create.side_effect = create_side_effect

    await service.register(
        email="rider@example.com",
        phone=None,
        password="StrongPass123!",
        role=UserRole.RIDER,
        first_name="Test",
        last_name="Rider",
    )

    otp_publish_call = publisher.publish.await_args_list[0]
    assert otp_publish_call.args[0] == Exchanges.AUTH
    assert otp_publish_call.args[1] == RoutingKeys.USER_OTP_REQUESTED
    assert otp_publish_call.args[2]["email"] == "rider@example.com"
    assert otp_publish_call.args[2]["otp_code"] == "482913"
    assert otp_publish_call.args[2]["purpose"] == "registration"
    assert otp_publish_call.args[2]["channel"] == "email"


@pytest.mark.asyncio
async def test_resend_otp_publishes_otp_requested_event():
    user_id = uuid4()
    credential_repo = MagicMock()
    credential_repo.get_by_id = AsyncMock(
        return_value=SimpleNamespace(
            id=user_id,
            email="rider@example.com",
            phone=None,
        )
    )
    token_repo = MagicMock()
    otp_service = MagicMock()
    otp_service.generate_otp = AsyncMock(return_value="654321")
    publisher = MagicMock()
    publisher.publish = AsyncMock()

    service = AuthService(
        credential_repo=credential_repo,
        token_repo=token_repo,
        otp_service=otp_service,
        jwt_handler=MagicMock(),
        publisher=publisher,
    )

    code = await service.resend_otp(user_id, "registration")

    assert code == "654321"
    publisher.publish.assert_awaited_once()
    exchange, routing_key, payload = publisher.publish.await_args.args
    assert exchange == Exchanges.AUTH
    assert routing_key == RoutingKeys.USER_OTP_REQUESTED
    assert payload["email"] == "rider@example.com"
    assert payload["otp_code"] == "654321"
    assert payload["purpose"] == "registration"


@pytest.mark.asyncio
async def test_register_unverified_existing_user_returns_otp_flag():
    user_id = uuid4()
    credential_repo = MagicMock()
    credential_repo.get_by_email_or_phone = AsyncMock(
        return_value=SimpleNamespace(
            id=user_id,
            is_verified=False,
        )
    )

    otp_service = MagicMock()
    # A registration code is still valid, so the pending sign-up is left alone.
    otp_service.otp_repo.get_latest_unverified = AsyncMock(
        return_value=SimpleNamespace(id=uuid4())
    )
    service = AuthService(
        credential_repo=credential_repo,
        token_repo=MagicMock(),
        otp_service=otp_service,
        jwt_handler=MagicMock(),
        publisher=MagicMock(),
    )

    with pytest.raises(ConflictError) as exc_info:
        await service.register(
            email="rider@example.com",
            phone=None,
            password="StrongPass123!",
            role=UserRole.RIDER,
        )

    assert exc_info.value.details == {
        "otp_verified": False,
        "user_id": str(user_id),
        "next_step": "verify_otp",
    }


@pytest.mark.asyncio
async def test_login_unverified_user_returns_otp_flag():
    user_id = uuid4()
    credential_repo = MagicMock()
    credential_repo.get_by_email_or_phone = AsyncMock(
        return_value=SimpleNamespace(
            id=user_id,
            email="rider@example.com",
            phone=None,
            password_hash="hashed:StrongPass123!",
            role=UserRole.RIDER,
            business_id=None,
            is_verified=False,
            is_active=True,
            failed_attempts=0,
            locked_until=None,
        )
    )

    service = AuthService(
        credential_repo=credential_repo,
        token_repo=MagicMock(),
        otp_service=MagicMock(),
        jwt_handler=MagicMock(),
        publisher=MagicMock(),
    )

    with pytest.raises(AuthenticationError) as exc_info:
        await service.login(
            email="rider@example.com",
            phone=None,
            password="StrongPass123!",
        )

    assert exc_info.value.details == {
        "otp_verified": False,
        "user_id": str(user_id),
        "next_step": "verify_otp",
    }


@pytest.mark.asyncio
async def test_register_normalizes_email_before_lookup_and_storage():
    user_id = uuid4()
    credential_repo = MagicMock()
    credential_repo.get_by_email_or_phone = AsyncMock(return_value=None)
    credential_repo.create = AsyncMock()
    token_repo = MagicMock()
    otp_service = MagicMock()
    otp_service.generate_otp = AsyncMock(return_value="482913")
    publisher = MagicMock()
    publisher.publish = AsyncMock()

    service = AuthService(
        credential_repo=credential_repo,
        token_repo=token_repo,
        otp_service=otp_service,
        jwt_handler=MagicMock(),
        publisher=publisher,
    )

    async def create_side_effect(credential):
        credential.id = user_id

    credential_repo.create.side_effect = create_side_effect

    await service.register(
        email="  Moses.OladunjoyeJobs@Gmail.com  ",
        phone=None,
        password="StrongPass123!",
        role=UserRole.RIDER,
    )

    credential_repo.get_by_email_or_phone.assert_awaited_once_with(
        "moses.oladunjoyejobs@gmail.com", None
    )
    created_credential = credential_repo.create.await_args.args[0]
    assert created_credential.email == "moses.oladunjoyejobs@gmail.com"


@pytest.mark.asyncio
async def test_login_normalizes_email_before_lookup():
    credential_repo = MagicMock()
    credential_repo.get_by_email_or_phone = AsyncMock(return_value=None)

    service = AuthService(
        credential_repo=credential_repo,
        token_repo=MagicMock(),
        otp_service=MagicMock(),
        jwt_handler=MagicMock(),
        publisher=MagicMock(),
    )

    with pytest.raises(AuthenticationError):
        await service.login(
            email="  Moses.OladunjoyeJobs@Gmail.com  ",
            phone=None,
            password="StrongPass123!",
        )

    credential_repo.get_by_email_or_phone.assert_awaited_once_with(
        "moses.oladunjoyejobs@gmail.com", None
    )


def _bare_service(credential=None, otp_service=None):
    credential_repo = MagicMock()
    credential_repo.get_by_id = AsyncMock(return_value=credential)
    return AuthService(
        credential_repo=credential_repo,
        token_repo=MagicMock(),
        otp_service=otp_service or MagicMock(),
        jwt_handler=MagicMock(),
        publisher=MagicMock(),
    )


@pytest.mark.asyncio
async def test_resend_otp_refuses_unlisted_purposes():
    from mediride_common.exceptions import ValidationError

    otp_service = MagicMock()
    otp_service.generate_otp = AsyncMock()
    service = _bare_service(
        SimpleNamespace(id=uuid4(), email="a@example.com", phone=None), otp_service
    )

    for purpose in ("driver_activation", "account_deletion", "anything"):
        with pytest.raises(ValidationError):
            await service.resend_otp(uuid4(), purpose)
    otp_service.generate_otp.assert_not_awaited()


@pytest.mark.asyncio
async def test_reset_password_for_unknown_id_looks_like_a_wrong_code():
    from mediride_common.exceptions import ValidationError

    service = _bare_service(credential=None)
    service._validate_password = AsyncMock()

    with pytest.raises(ValidationError) as exc:
        await service.reset_password(uuid4(), "123456", "N3w-Passw0rd!")
    assert "Invalid OTP code" in str(exc.value.message)


def test_placeholder_user_id_is_stable_and_looks_like_a_real_id():
    from app.api.v1.auth_endpoints import _placeholder_user_id

    first = _placeholder_user_id("Nobody@Example.com")
    assert first == _placeholder_user_id("nobody@example.com ")
    assert first != _placeholder_user_id("other@example.com")
    assert first.version == 4  # same version as real (uuid4) account ids


def _unverified(email="victim@example.com"):
    return SimpleNamespace(
        id=uuid4(),
        email=email,
        phone=None,
        is_verified=False,
        password_hash="hashed:attacker-password",
        role=UserRole.BUSINESS,
        business_id=None,
    )


def _registration_service(existing, pending_otp):
    credential_repo = MagicMock()
    credential_repo.get_by_email_or_phone = AsyncMock(return_value=existing)
    credential_repo.session = MagicMock()
    credential_repo.session.commit = AsyncMock()
    otp_service = MagicMock()
    otp_service.otp_repo = MagicMock()
    otp_service.otp_repo.get_latest_unverified = AsyncMock(return_value=pending_otp)
    otp_service.generate_otp = AsyncMock(return_value="246810")
    publisher = MagicMock()
    publisher.publish = AsyncMock()
    service = AuthService(
        credential_repo=credential_repo,
        token_repo=MagicMock(),
        otp_service=otp_service,
        jwt_handler=MagicMock(),
        publisher=publisher,
    )
    service._validate_password = AsyncMock()
    return service, credential_repo, otp_service, publisher


@pytest.mark.asyncio
async def test_register_over_abandoned_signup_replaces_password_and_role():
    existing = _unverified()
    service, repo, otp_service, publisher = _registration_service(existing, None)

    with pytest.raises(ConflictError):
        await service.register(
            email="victim@example.com",
            phone=None,
            password="the-real-owner-pw",
            role=UserRole.RIDER,
        )

    assert existing.password_hash != "hashed:attacker-password"
    assert existing.role == UserRole.RIDER
    otp_service.generate_otp.assert_awaited_once()
    repo.session.commit.assert_awaited_once()  # kept despite the 409 rollback
    publisher.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_does_not_overwrite_while_code_is_still_valid():
    existing = _unverified()
    service, repo, otp_service, publisher = _registration_service(
        existing, SimpleNamespace(id=uuid4())
    )

    with pytest.raises(ConflictError):
        await service.register(
            email="victim@example.com",
            phone=None,
            password="someone-else-pw",
            role=UserRole.RIDER,
        )

    assert existing.password_hash == "hashed:attacker-password"
    assert existing.role == UserRole.BUSINESS
    otp_service.generate_otp.assert_not_awaited()
    repo.session.commit.assert_not_awaited()
