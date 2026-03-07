from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from mediride_common.utils import utc_now


class NotificationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, notification: Notification) -> Notification:
        self.session.add(notification)
        await self.session.flush()
        await self.session.refresh(notification)
        return notification

    async def get_by_id(self, notification_id: UUID) -> Notification | None:
        result = await self.session.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: UUID,
        offset: int = 0,
        limit: int = 20,
        unread_only: bool = False,
        notification_type: str | None = None,
    ) -> tuple[list[Notification], int]:
        query = select(Notification).where(Notification.user_id == user_id)
        count_query = select(func.count(Notification.id)).where(
            Notification.user_id == user_id
        )

        if unread_only:
            query = query.where(Notification.is_read == False)  # noqa: E712
            count_query = count_query.where(Notification.is_read == False)  # noqa: E712

        if notification_type:
            query = query.where(Notification.notification_type == notification_type)
            count_query = count_query.where(
                Notification.notification_type == notification_type
            )

        query = query.order_by(Notification.created_at.desc()).offset(offset).limit(limit)

        result = await self.session.execute(query)
        notifications = list(result.scalars().all())

        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        return notifications, total

    async def mark_read(self, notification_id: UUID, user_id: UUID) -> bool:
        result = await self.session.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
            .values(is_read=True, read_at=utc_now())
        )
        return result.rowcount > 0

    async def mark_all_read(self, user_id: UUID) -> int:
        result = await self.session.execute(
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
            .values(is_read=True, read_at=utc_now())
        )
        return result.rowcount

    async def count_unread(self, user_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
        )
        return result.scalar() or 0
