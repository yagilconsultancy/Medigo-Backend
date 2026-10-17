import hashlib
import string
from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.services.common_passwords import is_common_password
from mediride_common.exceptions import ValidationError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


@dataclass(frozen=True)
class PasswordPolicy:
    """Password rules.

    The real values live in the security_settings table and are supplied by
    SecuritySettingsService. These defaults are what applies when no settings
    row exists or it cannot be read, so they must be the full owner-approved
    policy (security gap 6): 12+ characters with upper, lower, digit and
    symbol. Common passwords are always blocked, whatever the row says.
    """

    min_length: int = 12
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_numbers: bool = True
    require_special_chars: bool = True


# The lowest minimum length an admin may configure in Security Settings.
MIN_PASSWORD_LENGTH_FLOOR = 12

COMMON_PASSWORD_MESSAGE = (
    "This password is too common. Choose something harder to guess."
)


DEFAULT_PASSWORD_POLICY = PasswordPolicy()


def validate_password_strength(
    password: str,
    policy: PasswordPolicy | None = None,
    email: str | None = None,
) -> None:
    """Validate password meets the configured strength requirements.

    ``email`` is optional; when given, passwords built from the email's
    local part are rejected as too common.
    """
    rules = policy or DEFAULT_PASSWORD_POLICY

    if len(password) < rules.min_length:
        raise ValidationError(
            f"Password must be at least {rules.min_length} characters"
        )
    if rules.require_uppercase and not any(c.isupper() for c in password):
        raise ValidationError("Password must contain at least one uppercase letter")
    if rules.require_lowercase and not any(c.islower() for c in password):
        raise ValidationError("Password must contain at least one lowercase letter")
    if rules.require_numbers and not any(c.isdigit() for c in password):
        raise ValidationError("Password must contain at least one digit")
    if rules.require_special_chars and not any(
        c in string.punctuation for c in password
    ):
        raise ValidationError(
            "Password must contain at least one special character"
        )
    if is_common_password(password, email):
        raise ValidationError(COMMON_PASSWORD_MESSAGE)


def hash_token(token: str) -> str:
    """Hash a refresh token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()
