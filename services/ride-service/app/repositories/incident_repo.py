from uuid import UUID

from sqlalchemy import String as SAString, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incident import Incident
from app.models.incident_note import IncidentNote


class IncidentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def next_number(self) -> int:
        result = await self.session.execute(text("SELECT nextval('incident_seq')"))
        return result.scalar_one()

    async def create(self, incident: Incident) -> Incident:
        self.session.add(incident)
        await self.session.flush()
        await self.session.refresh(incident)
        return incident

    async def get_by_id(self, incident_id: UUID) -> Incident | None:
        result = await self.session.execute(
            select(Incident).where(Incident.id == incident_id)
        )
        return result.scalar_one_or_none()

    async def get_paginated(
        self,
        offset: int = 0,
        limit: int = 20,
        incident_type: str | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> tuple[list[Incident], int]:
        query = select(Incident)
        count_query = select(func.count(Incident.id))

        if incident_type:
            query = query.where(Incident.incident_type == incident_type)
            count_query = count_query.where(Incident.incident_type == incident_type)
        if status:
            query = query.where(Incident.status == status)
            count_query = count_query.where(Incident.status == status)
        if search:
            pattern = f"%{search}%"
            search_filter = (
                Incident.subject_name.ilike(pattern)
                | func.cast(Incident.incident_number, SAString).ilike(pattern)
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        total = (await self.session.execute(count_query)).scalar_one()
        rows = (
            await self.session.execute(
                query.order_by(Incident.created_at.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), total

    async def update_status(self, incident: Incident, status: str) -> Incident:
        incident.status = status
        await self.session.flush()
        await self.session.refresh(incident)
        return incident

    async def count_by_type(self, incident_type: str) -> int:
        result = await self.session.execute(
            select(func.count(Incident.id)).where(Incident.incident_type == incident_type)
        )
        return result.scalar_one()

    async def count_total(self) -> int:
        result = await self.session.execute(select(func.count(Incident.id)))
        return result.scalar_one()

    # ── Notes ──

    async def create_note(self, note: IncidentNote) -> IncidentNote:
        self.session.add(note)
        await self.session.flush()
        return note

    async def get_notes(self, incident_id: UUID) -> list[IncidentNote]:
        result = await self.session.execute(
            select(IncidentNote)
            .where(IncidentNote.incident_id == incident_id)
            .order_by(IncidentNote.created_at.desc())
        )
        return list(result.scalars().all())
