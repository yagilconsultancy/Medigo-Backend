import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from mediride_common.database.base import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)

    # Notification settings
    push_ride_updates: Mapped[bool] = mapped_column(Boolean, default=True)
    push_chat_messages: Mapped[bool] = mapped_column(Boolean, default=True)
    push_earnings: Mapped[bool] = mapped_column(Boolean, default=True)
    push_promotions: Mapped[bool] = mapped_column(Boolean, default=True)
    email_ride_receipts: Mapped[bool] = mapped_column(Boolean, default=True)
    email_weekly_summary: Mapped[bool] = mapped_column(Boolean, default=True)
    sms_ride_updates: Mapped[bool] = mapped_column(Boolean, default=False)

    # Privacy settings
    share_location_with_rider: Mapped[bool] = mapped_column(Boolean, default=True)
    show_profile_photo: Mapped[bool] = mapped_column(Boolean, default=True)
    show_rating: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_data_analytics: Mapped[bool] = mapped_column(Boolean, default=True)

    # App settings
    language: Mapped[str] = mapped_column(String(10), default="en")
    distance_unit: Mapped[str] = mapped_column(String(10), default="miles")
    theme: Mapped[str] = mapped_column(String(10), default="system")
    auto_accept_rides: Mapped[bool] = mapped_column(Boolean, default=False)
    navigation_app: Mapped[str] = mapped_column(String(20), default="google_maps")
    sound_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
