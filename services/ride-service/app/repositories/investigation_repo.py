from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.investigation import Investigation
from app.models.investigation_note import InvestigationNote


class InvestigationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def next_number(self) -> int:
        result = await self.session.execute(text("SELECT nextval('investigation_seq')"))
        return result.scalar_one()

    async def create(self, investigation: Investigation) -> Investigation:
        self.session.add(investigation)
        await self.session.flush()
        await self.session.refresh(investigation)
        return investigation

    async def get_by_id(self, inv_id: UUID) -> Investigation | None:
        result = await self.session.execute(
            select(Investigation).where(Investigation.id == inv_id)
        )
        return result.scalar_one_or_none()

    async def get_paginated(
        self,
        offset: int = 0,
        limit: int = 20,
        priority: str | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> tuple[list[Investigation], int]:
        query = select(Investigation)
        count_query = select(func.count(Investigation.id))

        if priority:
            query = query.where(Investigation.priority == priority)
            count_query = count_query.where(Investigation.priority == priority)
        if status:
            query = query.where(Investigation.status == status)
            count_query = count_query.where(Investigation.status == status)
        if search:
            pattern = f"%{search}%"
            search_filter = Investigation.subject_name.ilike(pattern)
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        total = (await self.session.execute(count_query)).scalar_one()
        rows = (
            await self.session.execute(
                query.order_by(Investigation.created_at.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), total

    async def count_active(self) -> int:
        result = await self.session.execute(
            select(func.count(Investigation.id)).where(
                Investigation.status.in_(["in_progress", "unassigned"])
            )
        )
        return result.scalar_one()

    async def count_by_status(self, status: str) -> int:
        result = await self.session.execute(
            select(func.count(Investigation.id)).where(Investigation.status == status)
        )
        return result.scalar_one()

    async def avg_duration_days(self) -> float:
        from sqlalchemy import extract
        result = await self.session.execute(
            select(
                func.coalesce(
                    func.avg(
                        extract("epoch", Investigation.completed_at - Investigation.opened_at) / 86400.0
                    ),
                    0,
                )
            ).where(Investigation.completed_at.isnot(None))
        )
        return round(float(result.scalar_one()), 1)

    async def update(self, investigation: Investigation) -> Investigation:
        await self.session.flush()
        await self.session.refresh(investigation)
        return investigation

    # ── Notes ──

    async def create_note(self, note: InvestigationNote) -> InvestigationNote:
        self.session.add(note)
        await self.session.flush()
        return note

    async def get_notes(self, investigation_id: UUID) -> list[InvestigationNote]:
        result = await self.session.execute(
            select(InvestigationNote)
            .where(InvestigationNote.investigation_id == investigation_id)
            .order_by(InvestigationNote.created_at.desc())
        )
        return list(result.scalars().all())
