"""Security Settings must actually govern behaviour.

The stored policy used to be decorative: password_service hardcoded a
minimum of 8 while the settings row said 12, session_timeout_hours never
reached JWT expiry, and require_special_chars was not checked at all.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.password_service import (
    DEFAULT_PASSWORD_POLICY,
    PasswordPolicy,
    validate_password_strength,
)
from app.services import security_policy_cache
from mediride_common.auth.jwt_handler import JWTHandler
from mediride_common.exceptions import ValidationError


# ── password policy ──────────────────────────────────────────────────────


def test_default_policy_preserves_historical_behaviour():
    validate_password_strength("SecurePass123")
    with pytest.raises(ValidationError, match="at least 8 characters"):
        validate_password_strength("Short1")


def test_configured_minimum_length_is_enforced():
    policy = PasswordPolicy(min_length=14)
    with pytest.raises(ValidationError, match="at least 14 characters"):
        validate_password_strength("SecurePass123", policy)  # 13 chars
    validate_password_strength("SecurePass1234", policy)


def test_require_special_chars_is_enforced_when_configured():
    policy = PasswordPolicy(require_special_chars=True)
    with pytest.raises(ValidationError, match="special character"):
        validate_password_strength("SecurePass123", policy)
    validate_password_strength("SecurePass123!", policy)


def test_relaxed_policy_can_disable_a_rule():
    policy = PasswordPolicy(require_numbers=False)
    validate_password_strength("SecurePassword", policy)


# ── policy cache ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_cache():
    security_policy_cache.invalidate_policy_cache()
    yield
    security_policy_cache.invalidate_policy_cache()


@pytest.mark.asyncio
async def test_policy_is_read_from_settings_row():
    row = SimpleNamespace(
        min_password_length=16, require_uppercase=True, require_lowercase=False,
        require_numbers=True, require_special_chars=True,
    )
    repo = MagicMock()
    repo.get_active = AsyncMock(return_value=row)
    with patch.object(security_policy_cache, "SecuritySettingsRepository", return_value=repo):
        policy = await security_policy_cache.get_password_policy(MagicMock())
    assert policy.min_length == 16
    assert policy.require_lowercase is False
    assert policy.require_special_chars is True


@pytest.mark.asyncio
async def test_policy_falls_back_to_defaults_when_settings_unavailable():
    """A settings outage must not block registration or password reset."""
    repo = MagicMock()
    repo.get_active = AsyncMock(side_effect=RuntimeError("db down"))
    with patch.object(security_policy_cache, "SecuritySettingsRepository", return_value=repo):
        policy = await security_policy_cache.get_password_policy(MagicMock())
    assert policy == DEFAULT_PASSWORD_POLICY


@pytest.mark.asyncio
async def test_invalidate_forces_a_reread():
    row = SimpleNamespace(
        min_password_length=10, require_uppercase=True, require_lowercase=True,
        require_numbers=True, require_special_chars=False,
    )
    repo = MagicMock()
    repo.get_active = AsyncMock(return_value=row)
    with patch.object(security_policy_cache, "SecuritySettingsRepository", return_value=repo):
        await security_policy_cache.get_password_policy(MagicMock())
        await security_policy_cache.get_password_policy(MagicMock())
        assert repo.get_active.await_count == 1  # served from cache

        security_policy_cache.invalidate_policy_cache()
        await security_policy_cache.get_password_policy(MagicMock())
        assert repo.get_active.await_count == 2


# ── session timeout ──────────────────────────────────────────────────────


def test_expire_minutes_overrides_token_lifetime_and_expires_in():
    handler = JWTHandler(secret_key="test-secret", access_token_expire_minutes=30)

    default_pair = handler.create_token_pair(user_id="u1", role="admin")
    assert default_pair.expires_in == 30 * 60

    # session_timeout_hours = 1
    pair = handler.create_token_pair(user_id="u1", role="admin", expire_minutes=60)
    assert pair.expires_in == 60 * 60

    payload = handler.decode_token(pair.access_token)
    lifetime = payload.exp - payload.iat
    assert lifetime == 3600, f"expected 3600s lifetime, got {lifetime}"
