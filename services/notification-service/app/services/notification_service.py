import logging
from uuid import UUID

from app.models.notification import Notification
from app.repositories.notification_repo import NotificationRepository
from mediride_common.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, repo: NotificationRepository):
        self.repo = repo

    async def create_notification(
        self,
        user_id: UUID,
        title: str,
        body: str,
        notification_type: str,
        data: dict | None = None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            title=title,
            body=body,
            notification_type=notification_type,
            data=data,
        )
        created = await self.repo.create(notification)
        logger.info(
            f"Created {notification_type} notification for user {user_id}: {title}"
        )
        return created

    async def list_notifications(
        self,
        user_id: UUID,
        offset: int = 0,
        limit: int = 20,
        unread_only: bool = False,
        notification_type: str | None = None,
    ) -> tuple[list[Notification], int]:
        return await self.repo.list_by_user(
            user_id, offset, limit, unread_only, notification_type
        )

    async def mark_read(self, notification_id: UUID, user_id: UUID) -> None:
        success = await self.repo.mark_read(notification_id, user_id)
        if not success:
            raise NotFoundError("Notification not found")

    async def mark_all_read(self, user_id: UUID) -> int:
        return await self.repo.mark_all_read(user_id)

    async def get_unread_count(self, user_id: UUID) -> int:
        return await self.repo.count_unread(user_id)
