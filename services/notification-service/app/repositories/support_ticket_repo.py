from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.support_ticket import SupportTicket


class SupportTicketRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, ticket: SupportTicket) -> SupportTicket:
        self.session.add(ticket)
        await self.session.flush()
        await self.session.refresh(ticket)
        return ticket

    async def get_by_id(self, ticket_id: UUID) -> SupportTicket | None:
        result = await self.session.execute(
            select(SupportTicket).where(SupportTicket.id == ticket_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: UUID, offset: int = 0, limit: int = 20) -> tuple[list[SupportTicket], int]:
        query = (
            select(SupportTicket)
            .where(SupportTicket.user_id == user_id)
            .order_by(SupportTicket.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(query)
        tickets = list(result.scalars().all())

        count_result = await self.session.execute(
            select(func.count(SupportTicket.id)).where(SupportTicket.user_id == user_id)
        )
        total = count_result.scalar() or 0
        return tickets, total
