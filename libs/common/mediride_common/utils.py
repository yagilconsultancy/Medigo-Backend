import uuid
from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def generate_uuid() -> uuid.UUID:
    return uuid.uuid4()


def generate_otp(length: int = 6) -> str:
    """Generate a numeric OTP code."""
    import secrets

    return "".join(str(secrets.randbelow(10)) for _ in range(length))
