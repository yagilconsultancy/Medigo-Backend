from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.security_settings_repo import SecuritySettingsRepository
from mediride_common.exceptions import NotFoundError


class SecuritySettingsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SecuritySettingsRepository(session)

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

        return {
            "two_fa_enabled_count": settings.two_fa_enabled_count,
            "total_admin_count": settings.total_admin_count,
            "password_policy": policy_level,
            "session_timeout_hours": settings.session_timeout_hours,
            "threats_blocked": settings.threats_blocked,
        }

    async def update_settings(self, admin_id: UUID, **updates) -> dict:
        await self.repo.update_settings(admin_id, **updates)
        return await self.get_settings()
