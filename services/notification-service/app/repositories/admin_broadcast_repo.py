from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_broadcast import AdminBroadcast


class AdminBroadcastRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, broadcast: AdminBroadcast) -> AdminBroadcast:
        self.session.add(broadcast)
        await self.session.flush()
        return broadcast

    async def get_by_type(
        self,
        broadcast_type: str,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[AdminBroadcast], int]:
        query = select(AdminBroadcast).where(AdminBroadcast.broadcast_type == broadcast_type)
        count_query = select(func.count(AdminBroadcast.id)).where(
            AdminBroadcast.broadcast_type == broadcast_type
        )

        total = (await self.session.execute(count_query)).scalar_one()
        rows = (
            await self.session.execute(
                query.order_by(AdminBroadcast.sent_at.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), total

    async def count_by_type(self, broadcast_type: str) -> int:
        result = await self.session.execute(
            select(func.count(AdminBroadcast.id)).where(
                AdminBroadcast.broadcast_type == broadcast_type
            )
        )
        return result.scalar_one()

    async def count_by_notification_type(self, broadcast_type: str, notification_type: str) -> int:
        result = await self.session.execute(
            select(func.count(AdminBroadcast.id)).where(
                AdminBroadcast.broadcast_type == broadcast_type,
                AdminBroadcast.notification_type == notification_type,
            )
        )
        return result.scalar_one()

    async def sum_delivered(self, broadcast_type: str) -> int:
        result = await self.session.execute(
            select(func.coalesce(func.sum(AdminBroadcast.delivered_count), 0)).where(
                AdminBroadcast.broadcast_type == broadcast_type
            )
        )
        return result.scalar_one()
