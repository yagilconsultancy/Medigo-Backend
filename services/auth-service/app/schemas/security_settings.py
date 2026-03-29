from pydantic import BaseModel


class SecurityKPIs(BaseModel):
    two_fa_enabled_count: int = 0
    total_admin_count: int = 8
    password_policy: str = "Strict"
    session_timeout_hours: int = 4
    threats_blocked: int = 0


class SecuritySettingsResponse(BaseModel):
    two_factor_enabled: bool = False
    ip_geo_blocking_enabled: bool = False
    ip_whitelist_enabled: bool = False
    audit_logging_enabled: bool = True
    session_timeout_hours: int = 4
    min_password_length: int = 12
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_numbers: bool = True
    require_special_chars: bool = True
    whitelisted_ips: dict | None = None
    two_fa_enabled_count: int = 0
    total_admin_count: int = 8
    threats_blocked: int = 0

    model_config = {"from_attributes": True}


class UpdateSecuritySettingsRequest(BaseModel):
    two_factor_enabled: bool | None = None
    ip_geo_blocking_enabled: bool | None = None
    ip_whitelist_enabled: bool | None = None
    audit_logging_enabled: bool | None = None
    session_timeout_hours: int | None = None
    min_password_length: int | None = None
    require_uppercase: bool | None = None
    require_lowercase: bool | None = None
    require_numbers: bool | None = None
    require_special_chars: bool | None = None
    whitelisted_ips: dict | None = None
