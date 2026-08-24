"""Process-local cache for the security settings singleton.

Password validation runs on every registration, invite and password change,
so reading the settings row each time would add a query to every one of those
paths. The row changes only when an admin saves the Security Settings form,
which also invalidates this cache explicitly; the short TTL is just a backstop
for other replicas.
"""

import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.security_settings_repo import SecuritySettingsRepository
from app.services.password_service import DEFAULT_PASSWORD_POLICY, PasswordPolicy

logger = logging.getLogger(__name__)

_TTL_SECONDS = 60.0

_cached_policy: PasswordPolicy | None = None
_cached_at: float = 0.0


def invalidate_policy_cache() -> None:
    """Call after the settings row is written."""
    global _cached_policy, _cached_at
    _cached_policy = None
    _cached_at = 0.0


async def get_password_policy(session: AsyncSession) -> PasswordPolicy:
    """Current password policy, falling back to defaults if unavailable."""
    global _cached_policy, _cached_at

    now = time.monotonic()
    if _cached_policy is not None and (now - _cached_at) < _TTL_SECONDS:
        return _cached_policy

    try:
        settings = await SecuritySettingsRepository(session).get_active()
    except Exception:
        # A settings lookup failure must not block logins or registrations.
        logger.warning("Could not load password policy; using defaults", exc_info=True)
        return DEFAULT_PASSWORD_POLICY

    if not settings:
        return DEFAULT_PASSWORD_POLICY

    policy = PasswordPolicy(
        min_length=settings.min_password_length,
        require_uppercase=settings.require_uppercase,
        require_lowercase=settings.require_lowercase,
        require_numbers=settings.require_numbers,
        require_special_chars=settings.require_special_chars,
    )
    _cached_policy = policy
    _cached_at = now
    return policy
