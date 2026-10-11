from uuid import uuid4

import pytest

from app.middleware import auth_middleware
from mediride_common.auth.jwt_handler import JWTHandler


@pytest.mark.asyncio
async def test_revoked_token_is_flagged(monkeypatch):
    handler = auth_middleware._jwt_handler
    user_id = str(uuid4())
    token = handler.create_access_token(user_id, "rider", None, "r@example.com")
    claims = handler.decode_to_claims(token)

    seen = {}

    async def fake_is_revoked(uid, iat, url):
        seen["args"] = (str(uid), iat)
        return True

    monkeypatch.setattr(auth_middleware, "is_token_revoked", fake_is_revoked)
    assert await auth_middleware.token_was_revoked(token, claims) is True
    assert seen["args"][0] == user_id
    assert isinstance(seen["args"][1], int)


@pytest.mark.asyncio
async def test_clean_token_passes(monkeypatch):
    handler = auth_middleware._jwt_handler
    token = handler.create_access_token(str(uuid4()), "rider", None, "r@example.com")
    claims = handler.decode_to_claims(token)

    async def fake_is_revoked(uid, iat, url):
        return False

    monkeypatch.setattr(auth_middleware, "is_token_revoked", fake_is_revoked)
    assert await auth_middleware.token_was_revoked(token, claims) is False
