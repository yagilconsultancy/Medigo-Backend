from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories.push_token_repo import PushTokenRepository
from mediride_common.auth.dependencies import get_current_user
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.responses import StandardResponse

router = APIRouter(prefix="/push-token")


class RegisterPushTokenRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=255)
    platform: str = Field(default="ios", pattern="^(ios|android)$")


class PushTokenResponse(BaseModel):
    user_id: str
    token: str
    platform: str

    model_config = {"from_attributes": True}


@router.post("", response_model=StandardResponse[PushTokenResponse])
async def register_push_token(
    body: RegisterPushTokenRequest,
    user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Register or update an Expo push token for the current user."""
    repo = PushTokenRepository(session)
    push_token = await repo.upsert(
        user_id=user.id,
        token=body.token,
        platform=body.platform,
    )
    return StandardResponse(
        data=PushTokenResponse(
            user_id=str(push_token.user_id),
            token=push_token.token,
            platform=push_token.platform,
        ),
        message="Push token registered",
    )


@router.delete("", response_model=StandardResponse)
async def remove_push_token(
    user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Remove the push token for the current user (e.g., on logout)."""
    repo = PushTokenRepository(session)
    await repo.delete_by_user_id(user.id)
    return StandardResponse(message="Push token removed")
