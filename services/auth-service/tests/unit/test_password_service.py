import pytest

from app.services.password_service import (
    hash_password,
    hash_token,
    validate_password_strength,
    verify_password,
)
from mediride_common.exceptions import ValidationError


def test_hash_and_verify_password():
    password = "SecurePass123"
    hashed = hash_password(password)
    assert verify_password(password, hashed)
    assert not verify_password("WrongPass", hashed)


def test_validate_password_strength_valid():
    validate_password_strength("SecurePass123")


def test_validate_password_strength_too_short():
    with pytest.raises(ValidationError, match="at least 8 characters"):
        validate_password_strength("Short1")


def test_validate_password_strength_no_uppercase():
    with pytest.raises(ValidationError, match="uppercase"):
        validate_password_strength("lowercase123")


def test_validate_password_strength_no_lowercase():
    with pytest.raises(ValidationError, match="lowercase"):
        validate_password_strength("UPPERCASE123")


def test_validate_password_strength_no_digit():
    with pytest.raises(ValidationError, match="digit"):
        validate_password_strength("NoDigitHere")


def test_hash_token():
    token = "some-refresh-token"
    hashed = hash_token(token)
    assert len(hashed) == 64  # SHA256 hex digest
    assert hash_token(token) == hashed  # Deterministic
