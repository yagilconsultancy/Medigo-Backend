import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.user_service_client import UserServiceClient
from app.config import settings
from app.repositories.notification_repo import NotificationRepository
from app.repositories.push_token_repo import PushTokenRepository
from app.services.email_service import send_admin_message_email
from app.services.notification_service import NotificationService
from app.services.push_service import send_expo_push
from mediride_common.schemas.enums import NotificationType

logger = logging.getLogger(__name__)


class AdminNotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.notification_service = NotificationService(NotificationRepository(session))
        self.push_token_repo = PushTokenRepository(session)
        self.user_client = UserServiceClient(settings.USER_SERVICE_URL)

    async def _send_to_user(
        self,
        user_id: UUID,
        title: str,
        message: str,
        admin_id: UUID,
    ) -> dict:
        """Send a notification to a user via in-app, email, and push.

        Returns a dict with notification_id, email_sent, and push_sent.
        """
        # 1. Create in-app notification
        notification = await self.notification_service.create_notification(
            user_id=user_id,
            title=title,
            body=message,
            notification_type=NotificationType.ADMIN_MESSAGE,
            data={"sent_by": str(admin_id), "screen": "notification_detail"},
        )

        email_sent = False
        push_sent = False

        # 2. Send email
        user_info = await self.user_client.get_user_email(user_id)
        if user_info and user_info.get("email"):
            try:
                email_sent = await send_admin_message_email(
                    to=user_info["email"],
                    recipient_name=user_info.get("name", "User"),
                    title=title,
                    message=message,
                )
            except Exception as e:
                logger.error("Failed to send admin message email to user %s: %s", user_id, e)

        # 3. Send Expo push notification
        push_token_record = await self.push_token_repo.get_by_user_id(user_id)
        if push_token_record:
            try:
                push_sent = await send_expo_push(
                    push_token=push_token_record.token,
                    title=title,
                    body=message,
                    data={"screen": "notification_detail", "notification_id": str(notification.id)},
                )
            except Exception as e:
                logger.error("Failed to send push notification to user %s: %s", user_id, e)

        return {
            "notification_id": notification.id,
            "email_sent": email_sent,
            "push_sent": push_sent,
        }

    async def send_to_driver(
        self,
        driver_id: UUID,
        title: str,
        message: str,
        admin_id: UUID,
    ) -> dict:
        """Send a notification to a specific driver."""
        result = await self._send_to_user(driver_id, title, message, admin_id)
        result["driver_id"] = driver_id
        return result

    async def send_to_rider(
        self,
        rider_id: UUID,
        title: str,
        message: str,
        admin_id: UUID,
    ) -> dict:
        """Send a notification to a specific rider."""
        result = await self._send_to_user(rider_id, title, message, admin_id)
        result["rider_id"] = rider_id
        return result
