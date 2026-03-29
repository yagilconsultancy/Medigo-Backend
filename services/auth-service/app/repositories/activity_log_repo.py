from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityLog


class ActivityLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, log: ActivityLog) -> ActivityLog:
        self.session.add(log)
        await self.session.flush()
        await self.session.refresh(log)
        return log

    async def get_next_log_number(self) -> int:
        result = await self.session.execute(text("SELECT nextval('activity_log_seq')"))
        return result.scalar()

    async def list_logs(
        self,
        severity: str | None = None,
        category: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[ActivityLog], int]:
        query = select(ActivityLog)
        count_query = select(func.count(ActivityLog.id))

        if severity:
            query = query.where(ActivityLog.severity == severity)
            count_query = count_query.where(ActivityLog.severity == severity)

        if category:
            query = query.where(ActivityLog.category == category)
            count_query = count_query.where(ActivityLog.category == category)

        if search:
            search_filter = or_(
                ActivityLog.action_title.ilike(f"%{search}%"),
                ActivityLog.action_description.ilike(f"%{search}%"),
                ActivityLog.admin_name.ilike(f"%{search}%"),
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        total = (await self.session.execute(count_query)).scalar() or 0
        rows = (
            await self.session.execute(
                query.order_by(ActivityLog.created_at.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), total

    async def get_severity_counts(self) -> dict[str, int]:
        result = await self.session.execute(
            select(ActivityLog.severity, func.count(ActivityLog.id)).group_by(ActivityLog.severity)
        )
        return {row[0]: row[1] for row in result.all()}

    async def get_total_count(self) -> int:
        result = await self.session.execute(select(func.count(ActivityLog.id)))
        return result.scalar() or 0
