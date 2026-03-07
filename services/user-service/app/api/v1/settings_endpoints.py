from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories.settings_repo import SettingsRepository
from app.schemas.settings import (
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


@router.get("", response_model=StandardResponse[UserSettingsResponse])
async def get_settings(
    user: UserClaims = Depends(get_current_user),
    repo: SettingsRepository = Depends(_get_repo),
):
    settings = await repo.get_or_create(user.id)
    return StandardResponse(data=UserSettingsResponse.model_validate(settings))


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
