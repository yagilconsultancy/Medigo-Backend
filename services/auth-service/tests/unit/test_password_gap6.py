"""Security gap 6: 12+ characters, all character classes, common passwords
blocked, and Security Settings cannot drop the minimum below 12."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.schemas.auth import (
    AdminRegisterRequest,
    ChangePasswordRequest,
    DriverActivationCompleteRequest,
    DriverRegisterRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.services.common_passwords import is_common_password
from app.services.password_service import (
    COMMON_PASSWORD_MESSAGE,
    PasswordPolicy,
    validate_password_strength,
)
from app.services.security_settings_service import SecuritySettingsService
from mediride_common.exceptions import ValidationError


# ── common-password block ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "password",
    [
        "Password123!",
        "PASSWORD123!x",
        "P@ssw0rd2024!",
        "Qwerty12345!",
        "Medigo2026!!",
        "MediGo#Rocks9",
        "Welcome123!@",
        "Summer2025!!!",
        "Iloveyou123!",
        "Aaaaaaaaaaa1!",
        "Abcdefghijk1!",
    ],
)
def test_common_passwords_are_rejected(password):
    with pytest.raises(ValidationError) as exc:
        validate_password_strength(password)
    assert exc.value.message == COMMON_PASSWORD_MESSAGE


def test_common_check_is_case_insensitive():
    assert is_common_password("pAsSwOrD123!")
    assert is_common_password("MONKEY!!12345")


def test_email_local_part_is_rejected():
    with pytest.raises(ValidationError, match="too common"):
        validate_password_strength("JaneDoe#2026x", email="jane.doe@example.com")
    # Same password is fine for someone else.
    validate_password_strength("JaneDoe#2026x", email="sam@example.com")


def test_short_email_local_part_is_ignored():
    validate_password_strength("Granite-Kettle7", email="al@example.com")


def test_common_block_applies_even_with_relaxed_policy():
    relaxed = PasswordPolicy(
        min_length=12, require_uppercase=False, require_lowercase=False,
        require_numbers=False, require_special_chars=False,
    )
    with pytest.raises(ValidationError, match="too common"):
        validate_password_strength("passwordpassword", relaxed)


@pytest.mark.parametrize(
    "password",
    ["Granite-Kettle7", "Tr0ub4dor&3-horse", "Badminton2024!", "SecurePass123!"],
)
def test_reasonable_passwords_are_allowed(password):
    validate_password_strength(password)


def test_generated_admin_temp_password_shape_passes():
    # Mirrors user-service generate_temporary_password and the driver
    # placeholder (token_urlsafe(24) + "aA1!"); both must keep passing.
    validate_password_strength("Hk7!pQz@Wm3#Rt9$Lx2a", email="new.admin@medigo.ca")
    validate_password_strength(
        "Zx9_kP2-vR8qL4tW7nB3mJ6cF1yH5dG0aA1!", email="driver@fleet.ca"
    )


# ── pydantic input bounds ────────────────────────────────────────────────


def test_new_password_fields_require_12_chars():
    short = "Abcdef1!xyz"  # 11
    with pytest.raises(PydanticValidationError):
        RegisterRequest(email="a@b.com", password=short)
    with pytest.raises(PydanticValidationError):
        ChangePasswordRequest(current_password="old", new_password=short)
    with pytest.raises(PydanticValidationError):
        ResetPasswordRequest(user_id=uuid4(), code="123456", new_password=short)
    with pytest.raises(PydanticValidationError):
        DriverRegisterRequest(invite_token="t", password=short)
    with pytest.raises(PydanticValidationError):
        AdminRegisterRequest(invite_token="t", password=short)
    with pytest.raises(PydanticValidationError):
        DriverActivationCompleteRequest(email="a@b.com", otp="123456", password=short)


def test_login_still_accepts_short_existing_passwords():
    req = LoginRequest(email="a@b.com", password="Old1pass")
    assert req.password == "Old1pass"
    # Changing away from a short password: current_password is unbounded.
    ChangePasswordRequest(current_password="Old1pass", new_password="Granite-Kettle7")


# ── Security Settings floor ──────────────────────────────────────────────


def _settings_service():
    svc = SecuritySettingsService.__new__(SecuritySettingsService)
    svc.session = MagicMock()
    svc.repo = MagicMock()
    svc.repo.update_settings = AsyncMock()
    svc.repo.get_active = AsyncMock(
        return_value=SimpleNamespace(
            two_factor_enabled=False, ip_geo_blocking_enabled=False,
            ip_whitelist_enabled=False, audit_logging_enabled=True,
            session_timeout_hours=4, max_failed_login_attempts=5,
            min_password_length=12, require_uppercase=True,
            require_lowercase=True, require_numbers=True,
            require_special_chars=True, whitelisted_ips=None,
            two_fa_enabled_count=0, total_admin_count=0, threats_blocked=0,
        )
    )
    return svc


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [8, 10, 11, 0, -1, None])
async def test_settings_refuse_min_length_below_12(value):
    svc = _settings_service()
    with pytest.raises(ValidationError, match="cannot be lower than 12"):
        await svc.update_settings(uuid4(), min_password_length=value)
    svc.repo.update_settings.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [12, 16])
async def test_settings_accept_min_length_12_or_more(value):
    svc = _settings_service()
    with patch(
        "app.services.security_settings_service.invalidate_policy_cache"
    ) as inval:
        data = await svc.update_settings(uuid4(), min_password_length=value)
    svc.repo.update_settings.assert_awaited_once()
    inval.assert_called_once()
    assert data["min_password_length"] == 12  # from the mocked row


@pytest.mark.asyncio
async def test_settings_update_without_length_is_unaffected():
    svc = _settings_service()
    with patch("app.services.security_settings_service.invalidate_policy_cache"):
        await svc.update_settings(uuid4(), two_factor_enabled=True)
    svc.repo.update_settings.assert_awaited_once()
