from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.disciplinary_action import DisciplinaryAction
from app.repositories.disciplinary_action_repo import DisciplinaryActionRepository


class AdminDisciplineService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DisciplinaryActionRepository(session)

    async def get_kpis(self) -> dict:
        total = await self.repo.count_total()
        suspensions = (
            await self.repo.count_by_type("account_suspension")
            + await self.repo.count_by_type("driving_suspension")
        )
        warnings = await self.repo.count_by_type("written_warning")
        reinstated = await self.repo.count_by_status("reinstated")
        return {
            "total": total,
            "suspensions": suspensions,
            "warnings": warnings,
            "reinstated": reinstated,
        }

    async def get_list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        search: str | None = None,
    ) -> dict:
        offset = (page - 1) * page_size
        items, total = await self.repo.get_paginated(
            offset=offset, limit=page_size, status=status, search=search,
        )
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def create_action(
        self, data: dict, admin_id: UUID, admin_name: str,
    ) -> DisciplinaryAction:
        number = await self.repo.next_number()
        action = DisciplinaryAction(
            action_number=number,
            incident_id=data.get("incident_id"),
            incident_number=data.get("incident_number"),
            investigation_id=data.get("investigation_id"),
            action_type=data["action_type"],
            severity=data["severity"],
            status="issued",
            subject_name=data["subject_name"],
            subject_id=data["subject_id"],
            subject_type=data["subject_type"],
            issued_by_name=admin_name,
            issued_by_id=admin_id,
            duration_text=data["duration_text"],
            duration_days=data.get("duration_days"),
            expires_at=data.get("expires_at"),
            reason=data.get("reason"),
        )
        return await self.repo.create(action)

    async def get_detail(self, action_id: UUID) -> DisciplinaryAction | None:
        return await self.repo.get_by_id(action_id)

    async def get_reason(self, action_id: UUID) -> str | None:
        action = await self.repo.get_by_id(action_id)
        if not action:
            return None
        return action.reason

    async def reinstate(self, action_id: UUID) -> DisciplinaryAction | None:
        action = await self.repo.get_by_id(action_id)
        if not action:
            return None
        return await self.repo.reinstate(action)

    async def get_detail_toggle(self, action_id: UUID) -> DisciplinaryAction | None:
        return await self.repo.get_by_id(action_id)
