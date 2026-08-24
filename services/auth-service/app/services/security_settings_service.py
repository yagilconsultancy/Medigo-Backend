from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.credential_repo import CredentialRepository
from app.repositories.login_record_repo import LoginRecordRepository
from app.repositories.security_settings_repo import SecuritySettingsRepository
from app.services.security_policy_cache import invalidate_policy_cache
from mediride_common.exceptions import NotFoundError


class SecuritySettingsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SecuritySettingsRepository(session)
        self.credential_repo = CredentialRepository(session)
        self.login_repo = LoginRecordRepository(session)

    async def get_settings(self) -> dict:
        settings = await self.repo.get_active()
        if not settings:
            raise NotFoundError("Security settings not initialized")
        return {
            "two_factor_enabled": settings.two_factor_enabled,
            "ip_geo_blocking_enabled": settings.ip_geo_blocking_enabled,
            "ip_whitelist_enabled": settings.ip_whitelist_enabled,
            "audit_logging_enabled": settings.audit_logging_enabled,
            "session_timeout_hours": settings.session_timeout_hours,
            "max_failed_login_attempts": settings.max_failed_login_attempts,
            "min_password_length": settings.min_password_length,
            "require_uppercase": settings.require_uppercase,
            "require_lowercase": settings.require_lowercase,
            "require_numbers": settings.require_numbers,
            "require_special_chars": settings.require_special_chars,
            "whitelisted_ips": settings.whitelisted_ips,
            "two_fa_enabled_count": settings.two_fa_enabled_count,
            "total_admin_count": settings.total_admin_count,
            "threats_blocked": settings.threats_blocked,
        }

    async def get_kpis(self) -> dict:
        settings = await self.repo.get_active()
        if not settings:
            raise NotFoundError("Security settings not initialized")

        policy_level = "Strict"
        if settings.min_password_length < 10:
            policy_level = "Basic"
        elif not (settings.require_uppercase and settings.require_special_chars):
            policy_level = "Moderate"

        # These used to echo constants seeded by migration 005 (a hardcoded
        # total_admin_count=8 and threats_blocked=14) that nothing ever
        # recomputed. Derive them from real data instead.
        total_admins = await self.credential_repo.count_active_admins()
        # 2FA is a global switch, not per-admin, so it is all-or-nothing.
        two_fa_count = total_admins if settings.two_factor_enabled else 0
        threats_blocked = await self.login_repo.count_blocked_recent(days=30)

        return {
            "two_fa_enabled_count": two_fa_count,
            "total_admin_count": total_admins,
            "password_policy": policy_level,
            "session_timeout_hours": settings.session_timeout_hours,
            "threats_blocked": threats_blocked,
        }

    async def update_settings(self, admin_id: UUID, **updates) -> dict:
        await self.repo.update_settings(admin_id, **updates)
        # Password rules are cached per-process; drop it so the new policy
        # takes effect immediately rather than after the TTL.
        invalidate_policy_cache()
        return await self.get_settings()
