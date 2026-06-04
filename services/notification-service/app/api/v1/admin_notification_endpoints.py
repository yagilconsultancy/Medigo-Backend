from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.admin_notification import (
    SendDriverNotificationRequest,
    SendDriverNotificationResponse,
    SendRiderNotificationRequest,
    SendRiderNotificationResponse,
)
from app.services.admin_notification_service import AdminNotificationService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> AdminNotificationService:
    return AdminNotificationService(session)


@router.post(
    "/notifications/send-to-driver",
    response_model=StandardResponse[SendDriverNotificationResponse],
)
async def send_notification_to_driver(
    body: SendDriverNotificationRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminNotificationService = Depends(_get_service),
):
    """Send a notification to a specific driver via in-app, email, and push."""
    result = await service.send_to_driver(
        driver_id=body.driver_id,
        title=body.title,
        message=body.message,
        admin_id=user.id,
    )
    return StandardResponse(
        data=SendDriverNotificationResponse(**result),
        message="Notification sent to driver",
    )


@router.post(
    "/notifications/send-to-rider",
    response_model=StandardResponse[SendRiderNotificationResponse],
)
async def send_notification_to_rider(
    body: SendRiderNotificationRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminNotificationService = Depends(_get_service),
):
    """Send a notification to a specific rider via in-app, email, and push."""
    result = await service.send_to_rider(
        rider_id=body.rider_id,
        title=body.title,
        message=body.message,
        admin_id=user.id,
    )
    return StandardResponse(
        data=SendRiderNotificationResponse(**result),
        message="Notification sent to rider",
    )
