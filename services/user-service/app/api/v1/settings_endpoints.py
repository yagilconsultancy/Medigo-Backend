from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories.settings_repo import SettingsRepository
from app.schemas.settings import (
    CommunicationSettingsResponse,
    UpdateCommunicationSettings,
    UpdateAppSettings,
    UpdateNotificationSettings,
    UpdatePrivacySettings,
    UserSettingsResponse,
)
from mediride_common.auth.dependencies import get_current_user
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.responses import StandardResponse

router = APIRouter(prefix="/me/settings")


def _get_repo(session: AsyncSession = Depends(get_db)) -> SettingsRepository:
    return SettingsRepository(session)


def _to_communication_response(settings) -> CommunicationSettingsResponse:
    return CommunicationSettingsResponse(
        sms_alerts=settings.sms_ride_updates,
        push_notifications=bool(settings.push_ride_updates or settings.push_chat_messages),
        promotional_emails=settings.email_weekly_summary,
    )


@router.get("", response_model=StandardResponse[UserSettingsResponse])
async def get_settings(
    user: UserClaims = Depends(get_current_user),
    repo: SettingsRepository = Depends(_get_repo),
):
    settings = await repo.get_or_create(user.id)
    return StandardResponse(data=UserSettingsResponse.model_validate(settings))


@router.get("/communication", response_model=StandardResponse[CommunicationSettingsResponse])
async def get_communication_settings(
    user: UserClaims = Depends(get_current_user),
    repo: SettingsRepository = Depends(_get_repo),
):
    settings = await repo.get_or_create(user.id)
    return StandardResponse(data=_to_communication_response(settings))


@router.put("/communication", response_model=StandardResponse[CommunicationSettingsResponse])
async def update_communication_settings(
    body: UpdateCommunicationSettings,
    user: UserClaims = Depends(get_current_user),
    repo: SettingsRepository = Depends(_get_repo),
):
    await repo.get_or_create(user.id)
    update_data = {}
    if body.sms_alerts is not None:
        update_data["sms_ride_updates"] = body.sms_alerts
    if body.push_notifications is not None:
        update_data["push_ride_updates"] = body.push_notifications
        update_data["push_chat_messages"] = body.push_notifications
    if body.promotional_emails is not None:
        update_data["email_weekly_summary"] = body.promotional_emails

    if update_data:
        await repo.update(user.id, **update_data)

    settings = await repo.get_by_user_id(user.id)
    return StandardResponse(
        data=_to_communication_response(settings),
        message="Communication settings updated",
    )


@router.put("/notifications", response_model=StandardResponse[UserSettingsResponse])
async def update_notification_settings(
    body: UpdateNotificationSettings,
    user: UserClaims = Depends(get_current_user),
    repo: SettingsRepository = Depends(_get_repo),
):
    await repo.get_or_create(user.id)
    update_data = body.model_dump(exclude_unset=True)
    if update_data:
        await repo.update(user.id, **update_data)
    settings = await repo.get_by_user_id(user.id)
    return StandardResponse(
        data=UserSettingsResponse.model_validate(settings),
        message="Notification settings updated",
    )


@router.put("/privacy", response_model=StandardResponse[UserSettingsResponse])
async def update_privacy_settings(
    body: UpdatePrivacySettings,
    user: UserClaims = Depends(get_current_user),
    repo: SettingsRepository = Depends(_get_repo),
):
    await repo.get_or_create(user.id)
    update_data = body.model_dump(exclude_unset=True)
    if update_data:
        await repo.update(user.id, **update_data)
    settings = await repo.get_by_user_id(user.id)
    return StandardResponse(
        data=UserSettingsResponse.model_validate(settings),
        message="Privacy settings updated",
    )


@router.put("/app", response_model=StandardResponse[UserSettingsResponse])
async def update_app_settings(
    body: UpdateAppSettings,
    user: UserClaims = Depends(get_current_user),
    repo: SettingsRepository = Depends(_get_repo),
):
    await repo.get_or_create(user.id)
    update_data = body.model_dump(exclude_unset=True)
    if update_data:
        await repo.update(user.id, **update_data)
    settings = await repo.get_by_user_id(user.id)
    return StandardResponse(
        data=UserSettingsResponse.model_validate(settings),
        message="App settings updated",
    )
