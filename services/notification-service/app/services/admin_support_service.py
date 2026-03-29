from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.support_ticket_repo import SupportTicketRepository


class AdminSupportService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SupportTicketRepository(session)

    async def get_kpis(self) -> dict:
        status_counts = await self.repo.get_status_counts()
        ride_disputes = await self.repo.count_by_type("ride_dispute")

        total = sum(status_counts.values())
        open_count = status_counts.get("open", 0) + status_counts.get("under_review", 0)
        resolved_count = status_counts.get("resolved", 0)

        return {
            "total_tickets": total,
            "open": open_count,
            "resolved": resolved_count,
            "ride_disputes": ride_disputes,
        }

    async def list_tickets(
        self,
        status: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        offset = (page - 1) * page_size
        tickets, total = await self.repo.get_all_admin(
            status=status, search=search, offset=offset, limit=page_size
        )

        items = []
        for t in tickets:
            items.append({
                "id": t.id,
                "ticket_id": f"TKT-{t.ticket_number}" if t.ticket_number else str(t.id)[:8],
                "ticket_type": t.ticket_type,
                "subject": t.subject,
                "rider_name": t.rider_name,
                "driver_name": t.driver_name,
                "priority": t.priority,
                "status": t.status,
                "created_at": t.created_at,
            })

        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def reopen_ticket(self, ticket_id: UUID) -> dict:
        ticket = await self.repo.update_status(ticket_id, "open")
        return {"id": ticket.id, "status": ticket.status}

    async def resolve_ticket(self, ticket_id: UUID, admin_id: UUID, response: str | None = None) -> dict:
        ticket = await self.repo.resolve_ticket(ticket_id, admin_id, response)
        return {"id": ticket.id, "status": ticket.status, "resolved_at": ticket.resolved_at}
