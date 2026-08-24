"""Failed logins and lockout state must survive the request-scope rollback.

Failure paths in AuthService raise immediately after recording the attempt.
That exception unwinds through get_db(), which calls session.rollback(). Before
this fix nothing committed first, so:
  * every failed-login audit row was discarded (the Login History "failed"
    filter and KPI were permanently empty), and
  * increment_failed_attempts()/lock_account() were discarded too, which
    silently disabled account lockout and allowed unlimited brute-force.
"""

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
from app.services.auth_service import UNKNOWN_ADMIN_ID, AuthService
from mediride_common.exceptions import AuthenticationError
from mediride_common.schemas.enums import UserRole


@pytest.fixture(autouse=True)
def _stub_password_verify(monkeypatch):
    """Real argon2 raises InvalidHashError on the fake hashes used here."""
    monkeypatch.setattr(
        auth_service_module,
        "verify_password",
        lambda password, password_hash: password_hash == f"hashed:{password}",
    )


def _make_login_history_service():
    svc = MagicMock()
    svc.session = MagicMock()
    svc.session.commit = AsyncMock()
    svc.record_login = AsyncMock()
    svc.repo = MagicMock()
    svc.repo.count_recent_failures = AsyncMock(return_value=0)
    svc.repo.has_successful_login_from_ip = AsyncMock(return_value=True)
    return svc


def _make_service(login_history_service, credential=None):
    credential_repo = MagicMock()
    credential_repo.get_by_email_or_phone = AsyncMock(return_value=credential)
    credential_repo.increment_failed_attempts = AsyncMock()
    credential_repo.lock_account = AsyncMock()
    credential_repo.reset_failed_attempts = AsyncMock()
    credential_repo.session = MagicMock()
    credential_repo.session.commit = AsyncMock()
    return (
        AuthService(
            credential_repo=credential_repo,
            token_repo=MagicMock(),
            otp_service=MagicMock(),
            jwt_handler=MagicMock(),
            publisher=MagicMock(),
            login_history_service=login_history_service,
        ),
        credential_repo,
    )


@pytest.mark.asyncio
async def test_failed_admin_login_commits_audit_row():
    lhs = _make_login_history_service()
    service, _ = _make_service(lhs, credential=None)

    with pytest.raises(AuthenticationError):
        await service.admin_login(
            email="ghost@example.com", phone=None, password="whatever",
            ip_address="1.2.3.4", user_agent="Mozilla/5.0",
        )

    lhs.record_login.assert_awaited_once()
    # The row must be committed, or get_db()'s rollback discards it.
    lhs.session.commit.assert_awaited_once()
    assert lhs.record_login.await_args.kwargs["success"] is False


@pytest.mark.asyncio
async def test_unknown_email_uses_stable_sentinel_id():
    lhs = _make_login_history_service()
    service, _ = _make_service(lhs, credential=None)

    with pytest.raises(AuthenticationError):
        await service.admin_login(
            email="ghost@example.com", phone=None, password="x",
            ip_address="1.2.3.4", user_agent="",
        )

    assert lhs.record_login.await_args.kwargs["user_id"] == UNKNOWN_ADMIN_ID


@pytest.mark.asyncio
async def test_successful_login_does_not_commit_mid_request():
    """Success must leave the commit to get_db(), not force one early."""
    lhs = _make_login_history_service()
    credential = SimpleNamespace(
        id=uuid4(), email="admin@example.com", phone=None,
        password_hash="hashed:GoodPass123!", is_active=True, is_verified=True,
        role=UserRole.ADMIN, locked_until=None, failed_attempts=0, business_id=None,
    )
    service, _ = _make_service(lhs, credential=credential)
    service.jwt_handler.create_token_pair = MagicMock(
        return_value=SimpleNamespace(access_token="a", refresh_token="r", role=None)
    )
    service.token_repo.create = AsyncMock()

    await service.admin_login(
        email="admin@example.com", phone=None, password="GoodPass123!",
        ip_address="1.2.3.4", user_agent="",
    )

    assert lhs.record_login.await_args.kwargs["success"] is True
    lhs.session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_repeated_failures_flagged_suspicious():
    lhs = _make_login_history_service()
    lhs.repo.count_recent_failures = AsyncMock(return_value=2)  # this is the 3rd
    service, _ = _make_service(lhs, credential=None)

    with pytest.raises(AuthenticationError):
        await service.admin_login(
            email="target@example.com", phone=None, password="x",
            ip_address="9.9.9.9", user_agent="",
        )

    assert lhs.record_login.await_args.kwargs["is_suspicious"] is True


@pytest.mark.asyncio
async def test_rider_login_commits_lockout_state():
    """The rider path has no audit row, so it needs its own commit."""
    credential = SimpleNamespace(
        id=uuid4(), email="rider@example.com", phone=None,
        password_hash="hashed:RealPass1!", is_active=True, is_verified=True,
        role=UserRole.RIDER, locked_until=None, failed_attempts=4, business_id=None,
    )
    service, credential_repo = _make_service(None, credential=credential)

    with pytest.raises(AuthenticationError):
        await service.login(email="rider@example.com", phone=None, password="WrongPass")

    credential_repo.increment_failed_attempts.assert_awaited_once()
    credential_repo.lock_account.assert_awaited_once()
    # Without this commit the lock is rolled back -> unlimited brute-force.
    credential_repo.session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_audit_failure_does_not_mask_auth_error():
    """A logging failure must never turn a clean 401 into a 500."""
    lhs = _make_login_history_service()
    lhs.record_login = AsyncMock(side_effect=RuntimeError("db down"))
    service, _ = _make_service(lhs, credential=None)

    with pytest.raises(AuthenticationError):
        await service.admin_login(
            email="ghost@example.com", phone=None, password="x",
            ip_address="1.2.3.4", user_agent="",
        )
