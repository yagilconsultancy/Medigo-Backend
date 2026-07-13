from uuid import UUID

from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.fleet_application import FleetApplication
from app.models.fleet_document import FleetDocument


class FleetApplicationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, application: FleetApplication) -> FleetApplication:
        self.session.add(application)
        await self.session.flush()
        await self.session.refresh(application)
        return application

    async def get_by_id(self, app_id: UUID) -> FleetApplication | None:
        result = await self.session.execute(
            select(FleetApplication)
            .options(selectinload(FleetApplication.documents))
            .where(FleetApplication.id == app_id)
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        status_filter: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[FleetApplication], int]:
        conditions = []

        if status_filter:
            conditions.append(FleetApplication.status == status_filter)

        base_query = select(FleetApplication).where(*conditions) if conditions else select(FleetApplication)

        # Count
        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        # Paginated results
        result = await self.session.execute(
            base_query
            .options(selectinload(FleetApplication.documents))
            .order_by(desc(FleetApplication.created_at))
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, app_id: UUID, **kwargs) -> None:
        app = await self.get_by_id(app_id)
        if app:
            for key, value in kwargs.items():
                setattr(app, key, value)
            await self.session.flush()

    async def delete(self, app_id: UUID) -> None:
        app = await self.get_by_id(app_id)
        if app:
            await self.session.delete(app)
            await self.session.flush()

    async def get_kpis(self) -> dict:
        result = await self.session.execute(
            select(
                func.count().label("total"),
                func.count().filter(FleetApplication.status == "pending").label("pending"),
                func.count().filter(FleetApplication.status == "approved").label("approved"),
                func.count().filter(FleetApplication.status == "rejected").label("rejected"),
            )
        )
        row = result.one()
        return {
            "total_applications": row.total,
            "pending_review": row.pending,
            "approved": row.approved,
            "rejected": row.rejected,
        }
