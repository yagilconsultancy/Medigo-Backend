"""Dispatch settings model for auto-dispatch configuration."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from mediride_common.database.base import Base


class DispatchSettings(Base):
    """
    Stores auto-dispatch configuration.
    Only one active record should exist (singleton pattern).
    """

    __tablename__ = "dispatch_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    auto_dispatch_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Distance matching logic
    search_radius_km: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    # Priority rules (JSONB for flexibility)
    priority_rules: Mapped[dict] = mapped_column(
        JSONB,
        server_default='{"prioritize_by_rating": true, "prioritize_by_fleet": false, "match_vehicle_type": true}',
        nullable=False,
    )

    # Fallback behavior (JSONB)
    fallback_behavior: Mapped[dict] = mapped_column(
        JSONB,
        server_default='{"expand_search_radius": true, "notify_dispatch_team": false, "notify_rider": false}',
        nullable=False,
    )

    # Audit fields
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
