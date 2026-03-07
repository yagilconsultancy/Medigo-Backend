from pydantic import BaseModel, Field


class UserSettingsResponse(BaseModel):
    # Notification settings
    push_ride_updates: bool
    push_chat_messages: bool
    push_earnings: bool
    push_promotions: bool
    email_ride_receipts: bool
    email_weekly_summary: bool
    sms_ride_updates: bool

    # Privacy settings
    share_location_with_rider: bool
    show_profile_photo: bool
    show_rating: bool
    allow_data_analytics: bool

    # App settings
    language: str
    distance_unit: str
    theme: str
    auto_accept_rides: bool
    navigation_app: str
    sound_enabled: bool

    model_config = {"from_attributes": True}


class UpdateNotificationSettings(BaseModel):
    push_ride_updates: bool | None = None
    push_chat_messages: bool | None = None
    push_earnings: bool | None = None
    push_promotions: bool | None = None
    email_ride_receipts: bool | None = None
    email_weekly_summary: bool | None = None
    sms_ride_updates: bool | None = None


class UpdatePrivacySettings(BaseModel):
    share_location_with_rider: bool | None = None
    show_profile_photo: bool | None = None
    show_rating: bool | None = None
    allow_data_analytics: bool | None = None


class UpdateAppSettings(BaseModel):
    language: str | None = Field(None, max_length=10)
    distance_unit: str | None = Field(None, max_length=10)
    theme: str | None = Field(None, max_length=10)
    auto_accept_rides: bool | None = None
    navigation_app: str | None = Field(None, max_length=20)
    sound_enabled: bool | None = None
