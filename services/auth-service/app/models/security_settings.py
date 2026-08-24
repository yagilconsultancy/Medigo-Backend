import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from mediride_common.database.base import Base


class SecuritySettings(Base):
    __tablename__ = "security_settings"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, unique=True, index=True)

    # Authentication
    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ip_geo_blocking_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ip_whitelist_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    audit_logging_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Session controls
    session_timeout_hours: Mapped[int] = mapped_column(Integer, default=4)

    # Password policy
    min_password_length: Mapped[int] = mapped_column(Integer, default=12)
    require_uppercase: Mapped[bool] = mapped_column(Boolean, default=True)
    require_lowercase: Mapped[bool] = mapped_column(Boolean, default=True)
    require_numbers: Mapped[bool] = mapped_column(Boolean, default=True)
    require_special_chars: Mapped[bool] = mapped_column(Boolean, default=True)

    # IP whitelist
    whitelisted_ips: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # KPI statistics
    max_failed_login_attempts: Mapped[int] = mapped_column(Integer, default=5)
    two_fa_enabled_count: Mapped[int] = mapped_column(Integer, default=0)
    total_admin_count: Mapped[int] = mapped_column(Integer, default=0)
    threats_blocked: Mapped[int] = mapped_column(Integer, default=0)

    # Audit
    updated_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
