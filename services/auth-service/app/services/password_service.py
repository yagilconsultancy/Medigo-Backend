import hashlib

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from mediride_common.exceptions import ValidationError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def validate_password_strength(password: str) -> None:
    """Validate password meets minimum strength requirements."""
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters")
    if not any(c.isupper() for c in password):
        raise ValidationError("Password must contain at least one uppercase letter")
    if not any(c.islower() for c in password):
        raise ValidationError("Password must contain at least one lowercase letter")
    if not any(c.isdigit() for c in password):
        raise ValidationError("Password must contain at least one digit")


def hash_token(token: str) -> str:
    """Hash a refresh token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()
