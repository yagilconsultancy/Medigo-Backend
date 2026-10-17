from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services import auth_service as auth_module
from app.services.auth_service import AuthService
from mediride_common.exceptions import AuthenticationError
from mediride_common.utils import utc_now


def _service(stored_token, revoke_marker):
    service = AuthService.__new__(AuthService)
    service.jwt_handler = SimpleNamespace(
        decode_token=lambda token: SimpleNamespace(type="refresh")
    )
    session = SimpleNamespace(commit=AsyncMock())
    service.token_repo = SimpleNamespace(
        session=session,
        get_any_by_hash=AsyncMock(return_value=stored_token),
        revoke_all_for_user=AsyncMock(),
        revoke=AsyncMock(),
    )
    return service, session


@pytest.mark.asyncio
async def test_reused_old_token_revokes_every_session(monkeypatch):
    marker = AsyncMock()
    monkeypatch.setattr(auth_module, "revoke_user_tokens", marker)
    user_id = uuid4()
    stored = SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        revoked_at=utc_now() - timedelta(minutes=5),
        expires_at=utc_now() + timedelta(days=1),
    )
    service, session = _service(stored, marker)

    with pytest.raises(AuthenticationError):
        await service.refresh_token("old-token")

    service.token_repo.revoke_all_for_user.assert_awaited_once_with(user_id)
    marker.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_quick_retry_inside_grace_window_does_not_sign_everyone_out(
    monkeypatch,
):
    marker = AsyncMock()
    monkeypatch.setattr(auth_module, "revoke_user_tokens", marker)
    stored = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        revoked_at=utc_now() - timedelta(seconds=2),
        expires_at=utc_now() + timedelta(days=1),
    )
    service, session = _service(stored, marker)

    with pytest.raises(AuthenticationError):
        await service.refresh_token("just-rotated-token")

    service.token_repo.revoke_all_for_user.assert_not_awaited()
    marker.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_token_is_just_rejected(monkeypatch):
    marker = AsyncMock()
    monkeypatch.setattr(auth_module, "revoke_user_tokens", marker)
    service, session = _service(None, marker)

    with pytest.raises(AuthenticationError):
        await service.refresh_token("never-issued")

    service.token_repo.revoke_all_for_user.assert_not_awaited()
