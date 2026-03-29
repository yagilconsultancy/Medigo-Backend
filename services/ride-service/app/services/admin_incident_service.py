from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incident import Incident
from app.models.incident_note import IncidentNote
from app.repositories.incident_repo import IncidentRepository


class AdminIncidentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = IncidentRepository(session)

    async def get_kpis(self) -> dict:
        total = await self.repo.count_total()
        driver = await self.repo.count_by_type("driver_complaint")
        rider = await self.repo.count_by_type("rider_complaint")
        accidents = await self.repo.count_by_type("accident")
        return {
            "total": total,
            "driver_complaints": driver,
            "rider_complaints": rider,
            "accidents": accidents,
        }

    async def get_list(
        self,
        page: int = 1,
        page_size: int = 20,
        incident_type: str | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> dict:
        offset = (page - 1) * page_size
        items, total = await self.repo.get_paginated(
            offset=offset, limit=page_size,
            incident_type=incident_type, status=status, search=search,
        )
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def create_incident(
        self, data: dict, admin_id: UUID, admin_name: str,
    ) -> Incident:
        number = await self.repo.next_number()
        incident = Incident(
            incident_number=number,
            incident_type=data["incident_type"],
            severity=data["severity"],
            status="under_investigation",
            subject_name=data["subject_name"],
            subject_id=data.get("subject_id"),
            subject_type=data["subject_type"],
            filed_by_name=admin_name,
            filed_by_id=admin_id,
            filed_by_role="admin",
            ride_id=data.get("ride_id"),
            description=data["description"],
        )
        return await self.repo.create(incident)

    async def get_detail(self, incident_id: UUID) -> Incident | None:
        return await self.repo.get_by_id(incident_id)

    async def update_status(self, incident_id: UUID, status: str) -> Incident | None:
        incident = await self.repo.get_by_id(incident_id)
        if not incident:
            return None
        return await self.repo.update_status(incident, status)

    async def get_notes(self, incident_id: UUID) -> list[IncidentNote]:
        return await self.repo.get_notes(incident_id)

    async def add_note(
        self, incident_id: UUID, admin_id: UUID, admin_name: str, content: str,
    ) -> IncidentNote:
        note = IncidentNote(
            incident_id=incident_id,
            author_id=admin_id,
            author_name=admin_name,
            content=content,
        )
        return await self.repo.create_note(note)
