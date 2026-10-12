import time
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from mediride_common.auth import revocation


def _fake_client(get=None, set_result=True, fail=False):
    client = MagicMock()
    if fail:
        client.get = AsyncMock(side_effect=ConnectionError("down"))
        client.set = AsyncMock(side_effect=ConnectionError("down"))
    else:
        client.get = AsyncMock(return_value=get)
        client.set = AsyncMock(return_value=set_result)
    return client


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(revocation, "_clients", {})


def _use(monkeypatch, client):
    monkeypatch.setattr(revocation, "_client", lambda url: client)


@pytest.mark.asyncio
async def test_token_issued_before_marker_is_revoked(monkeypatch):
    now = int(time.time())
    _use(monkeypatch, _fake_client(get=str(now + 1)))
    assert await revocation.is_token_revoked(uuid4(), now - 60, "redis://x") is True


@pytest.mark.asyncio
async def test_token_issued_after_marker_is_fine(monkeypatch):
    now = int(time.time())
    _use(monkeypatch, _fake_client(get=str(now)))
    assert await revocation.is_token_revoked(uuid4(), now + 5, "redis://x") is False


@pytest.mark.asyncio
async def test_no_marker_means_not_revoked(monkeypatch):
    _use(monkeypatch, _fake_client(get=None))
    assert await revocation.is_token_revoked(uuid4(), 1, "redis://x") is False


@pytest.mark.asyncio
async def test_redis_down_fails_open(monkeypatch):
    _use(monkeypatch, _fake_client(fail=True))
    assert await revocation.is_token_revoked(uuid4(), 1, "redis://x") is False
    await revocation.revoke_user_tokens(uuid4(), "redis://x")  # must not raise
    assert await revocation.claim_single_use("k", "redis://x", 60) is True


@pytest.mark.asyncio
async def test_revoke_sets_marker_with_expiry(monkeypatch):
    client = _fake_client()
    _use(monkeypatch, client)
    user = uuid4()
    await revocation.revoke_user_tokens(user, "redis://x")
    key, value = client.set.await_args.args
    assert key == f"auth:revoked_before:{user}"
    assert int(value) >= int(time.time())
    assert client.set.await_args.kwargs["ex"] == revocation.MARKER_TTL_SECONDS


@pytest.mark.asyncio
async def test_single_use_claim_second_time_is_refused(monkeypatch):
    client = _fake_client(set_result=None)  # SET NX returns None when key exists
    _use(monkeypatch, client)
    assert await revocation.claim_single_use("k", "redis://x", 60) is False
