import os
import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "America/Toronto")


def utc_now() -> datetime:
    return datetime.now(UTC)


def app_timezone(tz_name: str = DEFAULT_TIMEZONE) -> ZoneInfo:
    return ZoneInfo(tz_name)


def local_now(tz_name: str = DEFAULT_TIMEZONE) -> datetime:
    return utc_now().astimezone(app_timezone(tz_name))


def ensure_timezone(dt: datetime, tz_name: str = DEFAULT_TIMEZONE) -> datetime:
    if dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=app_timezone(tz_name))


def normalize_to_utc(dt: datetime, tz_name: str = DEFAULT_TIMEZONE) -> datetime:
    return ensure_timezone(dt, tz_name).astimezone(UTC)


def start_of_local_day_utc(
    dt: datetime | None = None,
    tz_name: str = DEFAULT_TIMEZONE,
) -> datetime:
    local_dt = (dt or utc_now()).astimezone(app_timezone(tz_name))
    return local_dt.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


def generate_uuid() -> uuid.UUID:
    return uuid.uuid4()


def generate_otp(length: int = 6) -> str:
    """Generate a numeric OTP code."""
    import secrets

    return "".join(str(secrets.randbelow(10)) for _ in range(length))
