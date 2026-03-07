from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories.notification_repo import NotificationRepository
from app.schemas.notification import NotificationResponse, UnreadCountResponse
from app.services.notification_service import NotificationService
from mediride_common.auth.dependencies import get_current_user
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.responses import PaginatedResponse, StandardResponse

router = APIRouter(prefix="/inbox")


def _get_service(session: AsyncSession = Depends(get_db)) -> NotificationService:
    return NotificationService(NotificationRepository(session))


@router.get("", response_model=PaginatedResponse[NotificationResponse])
async def list_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    notification_type: str | None = Query(None),
    user: UserClaims = Depends(get_current_user),
    service: NotificationService = Depends(_get_service),
):
    offset = (page - 1) * limit
    notifications, total = await service.list_notifications(
        user.id, offset, limit, unread_only, notification_type
    )
    return PaginatedResponse(
        data=[NotificationResponse.model_validate(n) for n in notifications],
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.get("/unread-count", response_model=StandardResponse[UnreadCountResponse])
async def get_unread_count(
    user: UserClaims = Depends(get_current_user),
    service: NotificationService = Depends(_get_service),
):
    count = await service.get_unread_count(user.id)
    return StandardResponse(data=UnreadCountResponse(unread_count=count))


@router.put("/{notification_id}/read", response_model=StandardResponse)
async def mark_notification_read(
    notification_id: UUID,
    user: UserClaims = Depends(get_current_user),
    service: NotificationService = Depends(_get_service),
):
    await service.mark_read(notification_id, user.id)
    return StandardResponse(message="Notification marked as read")


@router.put("/read-all", response_model=StandardResponse[dict])
async def mark_all_read(
    user: UserClaims = Depends(get_current_user),
    service: NotificationService = Depends(_get_service),
):
    count = await service.mark_all_read(user.id)
    return StandardResponse(
        data={"notifications_read": count},
        message="All notifications marked as read",
    )
