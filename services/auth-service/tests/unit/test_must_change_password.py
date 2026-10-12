"""Admins created with a one-time password must change it at first login."""

import os
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

os.environ["DEBUG"] = "false"
os.environ["ENVIRONMENT"] = "development"

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

import app.services.auth_service as auth_service_module
from app.api.v1.internal_endpoints import CreateAdminCredentialRequest
from app.models.user_credential import UserCredential
from app.repositories.credential_repo import CredentialRepository
from app.schemas.auth import TokenResponse
from app.services.auth_service import AuthService
from mediride_common.auth.models import TokenPair
from mediride_common.schemas.enums import UserRole


@pytest.fixture(autouse=True)
def _stub_password_verify(monkeypatch):
    monkeypatch.setattr(
        auth_service_module,
        "verify_password",
        lambda password, password_hash: password_hash == f"hashed:{password}",
    )


def _service(credential):
    lhs = MagicMock()
    lhs.session = MagicMock()
    lhs.session.commit = AsyncMock()
    lhs.record_login = AsyncMock()
    lhs.repo = MagicMock()
    lhs.repo.count_recent_failures = AsyncMock(return_value=0)
    lhs.repo.has_successful_login_from_ip = AsyncMock(return_value=True)
    credential_repo = MagicMock()
    credential_repo.get_by_email_or_phone = AsyncMock(return_value=credential)
    credential_repo.reset_failed_attempts = AsyncMock()
    credential_repo.session = MagicMock()
    credential_repo.session.commit = AsyncMock()
    service = AuthService(
        credential_repo=credential_repo,
        token_repo=MagicMock(),
        otp_service=MagicMock(),
        jwt_handler=MagicMock(),
        publisher=MagicMock(),
        login_history_service=lhs,
    )
    service.jwt_handler.create_token_pair = MagicMock(
        return_value=TokenPair(access_token="a", refresh_token="r", expires_in=60)
    )
    service.token_repo.create = AsyncMock()
    return service


def _credential(must_change):
    return SimpleNamespace(
        id=uuid4(), email="new.admin@example.com", phone=None,
        password_hash="hashed:TempPass123!", is_active=True, is_verified=True,
        role=UserRole.ADMIN, locked_until=None, failed_attempts=0,
        business_id=None, must_change_password=must_change,
    )


@pytest.mark.asyncio
async def test_admin_login_reports_must_change_password():
    service = _service(_credential(True))
    pair = await service.admin_login(
        email="new.admin@example.com", phone=None, password="TempPass123!",
        ip_address="1.2.3.4", user_agent="",
    )
    assert pair.must_change_password is True


@pytest.mark.asyncio
async def test_admin_login_normal_account_not_flagged():
    service = _service(_credential(False))
    pair = await service.admin_login(
        email="new.admin@example.com", phone=None, password="TempPass123!",
        ip_address="1.2.3.4", user_agent="",
    )
    assert pair.must_change_password is False


def test_token_response_defaults_to_not_flagged():
    resp = TokenResponse(
        access_token="a", refresh_token="r", expires_in=60, role="rider"
    )
    assert resp.must_change_password is False


def test_internal_request_defaults_to_not_flagged():
    req = CreateAdminCredentialRequest(email="a@example.com", password="x")
    assert req.must_change_password is False


def test_column_exists_and_defaults_false():
    col = UserCredential.__table__.c.must_change_password
    assert col.nullable is False
    assert col.default.arg is False


@pytest.mark.asyncio
async def test_changing_password_clears_the_flag():
    session = MagicMock()
    session.execute = AsyncMock()
    repo = CredentialRepository(session)
    await repo.update_password(uuid4(), "new-hash")
    stmt = session.execute.await_args.args[0]
    params = stmt.compile().params
    assert params["must_change_password"] is False
    assert params["password_hash"] == "new-hash"
