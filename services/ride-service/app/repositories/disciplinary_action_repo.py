from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.disciplinary_action import DisciplinaryAction


class DisciplinaryActionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def next_number(self) -> int:
        result = await self.session.execute(text("SELECT nextval('disciplinary_seq')"))
        return result.scalar_one()

    async def create(self, action: DisciplinaryAction) -> DisciplinaryAction:
        self.session.add(action)
        await self.session.flush()
        await self.session.refresh(action)
        return action

    async def get_by_id(self, action_id: UUID) -> DisciplinaryAction | None:
        result = await self.session.execute(
            select(DisciplinaryAction).where(DisciplinaryAction.id == action_id)
        )
        return result.scalar_one_or_none()

    async def get_paginated(
        self,
        offset: int = 0,
        limit: int = 20,
        status: str | None = None,
        search: str | None = None,
    ) -> tuple[list[DisciplinaryAction], int]:
        query = select(DisciplinaryAction)
        count_query = select(func.count(DisciplinaryAction.id))

        if status:
            query = query.where(DisciplinaryAction.status == status)
            count_query = count_query.where(DisciplinaryAction.status == status)
        if search:
            pattern = f"%{search}%"
            search_filter = DisciplinaryAction.subject_name.ilike(pattern)
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        total = (await self.session.execute(count_query)).scalar_one()
        rows = (
            await self.session.execute(
                query.order_by(DisciplinaryAction.created_at.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), total

    async def count_total(self) -> int:
        result = await self.session.execute(select(func.count(DisciplinaryAction.id)))
        return result.scalar_one()

    async def count_by_type(self, action_type: str) -> int:
        result = await self.session.execute(
            select(func.count(DisciplinaryAction.id)).where(
                DisciplinaryAction.action_type == action_type
            )
        )
        return result.scalar_one()

    async def count_by_status(self, status: str) -> int:
        result = await self.session.execute(
            select(func.count(DisciplinaryAction.id)).where(
                DisciplinaryAction.status == status
            )
        )
        return result.scalar_one()

    async def reinstate(self, action: DisciplinaryAction) -> DisciplinaryAction:
        from datetime import datetime, timezone
        action.status = "reinstated"
        action.reinstated_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(action)
        return action

    async def update(self, action: DisciplinaryAction) -> DisciplinaryAction:
        await self.session.flush()
        await self.session.refresh(action)
        return action
