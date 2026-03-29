from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.investigation import Investigation
from app.models.investigation_note import InvestigationNote
from app.repositories.investigation_repo import InvestigationRepository


class AdminInvestigationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = InvestigationRepository(session)

    async def get_kpis(self) -> dict:
        active = await self.repo.count_active()
        assigned = await self.repo.count_by_status("in_progress")
        unassigned = await self.repo.count_by_status("unassigned")
        avg_dur = await self.repo.avg_duration_days()
        return {
            "active": active,
            "assigned": assigned,
            "unassigned": unassigned,
            "avg_duration_days": avg_dur,
        }

    async def get_list(
        self,
        page: int = 1,
        page_size: int = 20,
        priority: str | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> dict:
        offset = (page - 1) * page_size
        items, total = await self.repo.get_paginated(
            offset=offset, limit=page_size,
            priority=priority, status=status, search=search,
        )
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def get_detail(self, inv_id: UUID) -> Investigation | None:
        return await self.repo.get_by_id(inv_id)

    async def assign(self, inv_id: UUID, assigned_to_id: UUID, assigned_to_name: str) -> Investigation | None:
        inv = await self.repo.get_by_id(inv_id)
        if not inv:
            return None
        inv.assigned_to_id = assigned_to_id
        inv.assigned_to_name = assigned_to_name
        if inv.status == "unassigned":
            inv.status = "in_progress"
        return await self.repo.update(inv)

    async def update_status(self, inv_id: UUID, status: str) -> Investigation | None:
        inv = await self.repo.get_by_id(inv_id)
        if not inv:
            return None
        inv.status = status
        if status == "completed":
            inv.completed_at = datetime.now(timezone.utc)
            inv.progress_percent = 100
        return await self.repo.update(inv)

    async def update_progress(self, inv_id: UUID, progress: int) -> Investigation | None:
        inv = await self.repo.get_by_id(inv_id)
        if not inv:
            return None
        inv.progress_percent = min(max(progress, 0), 100)
        return await self.repo.update(inv)

    async def close(self, inv_id: UUID) -> Investigation | None:
        inv = await self.repo.get_by_id(inv_id)
        if not inv:
            return None
        inv.status = "closed"
        if not inv.completed_at:
            inv.completed_at = datetime.now(timezone.utc)
        inv.progress_percent = 100
        return await self.repo.update(inv)

    async def get_notes(self, inv_id: UUID) -> list[InvestigationNote]:
        return await self.repo.get_notes(inv_id)

    async def add_note(
        self, inv_id: UUID, admin_id: UUID, admin_name: str, content: str,
    ) -> InvestigationNote:
        note = InvestigationNote(
            investigation_id=inv_id,
            author_id=admin_id,
            author_name=admin_name,
            content=content,
        )
        return await self.repo.create_note(note)
