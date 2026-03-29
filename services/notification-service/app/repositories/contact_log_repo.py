from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact_log import ContactLog


class ContactLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, log: ContactLog) -> ContactLog:
        self.session.add(log)
        await self.session.flush()
        await self.session.refresh(log)
        return log

    async def get_next_contact_number(self) -> int:
        result = await self.session.execute(text("SELECT nextval('contact_log_seq')"))
        return result.scalar()

    async def list_recent(
        self, offset: int = 0, limit: int = 50
    ) -> tuple[list[ContactLog], int]:
        total = (
            await self.session.execute(select(func.count(ContactLog.id)))
        ).scalar() or 0

        rows = (
            await self.session.execute(
                select(ContactLog)
                .order_by(ContactLog.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), total

    async def get_channel_counts(self) -> dict[str, int]:
        result = await self.session.execute(
            select(ContactLog.channel, func.count(ContactLog.id)).group_by(ContactLog.channel)
        )
        return {row[0]: row[1] for row in result.all()}
