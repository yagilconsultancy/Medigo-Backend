from uuid import UUID

from sqlalchemy import func, or_, select, text, update
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

    # ── Admin methods ──

    async def get_next_ticket_number(self) -> int:
        result = await self.session.execute(text("SELECT nextval('support_ticket_seq')"))
        return result.scalar()

    async def get_all_admin(
        self,
        status: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[SupportTicket], int]:
        query = select(SupportTicket)
        count_query = select(func.count(SupportTicket.id))

        if status:
            query = query.where(SupportTicket.status == status)
            count_query = count_query.where(SupportTicket.status == status)

        if search:
            search_filter = or_(
                SupportTicket.subject.ilike(f"%{search}%"),
                SupportTicket.rider_name.ilike(f"%{search}%"),
                SupportTicket.driver_name.ilike(f"%{search}%"),
            )
            # Allow search by ticket number (TKT-XXXX or just digits)
            cleaned = search.replace("TKT-", "").replace("tkt-", "").strip()
            if cleaned.isdigit():
                search_filter = or_(
                    search_filter,
                    SupportTicket.ticket_number == int(cleaned),
                )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        total = (await self.session.execute(count_query)).scalar() or 0
        rows = (
            await self.session.execute(
                query.order_by(SupportTicket.created_at.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), total

    async def get_status_counts(self) -> dict[str, int]:
        result = await self.session.execute(
            select(SupportTicket.status, func.count(SupportTicket.id)).group_by(SupportTicket.status)
        )
        return {row[0]: row[1] for row in result.all()}

    async def count_by_type(self, ticket_type: str) -> int:
        result = await self.session.execute(
            select(func.count(SupportTicket.id)).where(SupportTicket.ticket_type == ticket_type)
        )
        return result.scalar() or 0

    async def update_status(self, ticket_id: UUID, status: str) -> SupportTicket | None:
        await self.session.execute(
            update(SupportTicket).where(SupportTicket.id == ticket_id).values(status=status)
        )
        ticket = await self.get_by_id(ticket_id)
        if ticket:
            await self.session.refresh(ticket)
        return ticket

    async def resolve_ticket(self, ticket_id: UUID, admin_id: UUID, response: str | None = None) -> SupportTicket | None:
        await self.session.execute(
            update(SupportTicket)
            .where(SupportTicket.id == ticket_id)
            .values(
                status="resolved",
                resolved_by=admin_id,
                resolved_at=func.now(),
                response=response,
            )
        )
        ticket = await self.get_by_id(ticket_id)
        if ticket:
            await self.session.refresh(ticket)
        return ticket
