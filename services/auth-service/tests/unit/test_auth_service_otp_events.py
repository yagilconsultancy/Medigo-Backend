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
    otp_service.generate_otp = AsyncMock(return_value="123456")
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
    assert otp_publish_call.args[2]["otp_code"] == "123456"
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

    service = AuthService(
        credential_repo=credential_repo,
        token_repo=MagicMock(),
        otp_service=MagicMock(),
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
