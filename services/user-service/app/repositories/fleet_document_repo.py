from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fleet_document import FleetDocument


class FleetDocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, doc: FleetDocument) -> FleetDocument:
        self.session.add(doc)
        await self.session.flush()
        await self.session.refresh(doc)
        return doc

    async def get_by_id(self, doc_id: UUID) -> FleetDocument | None:
        result = await self.session.execute(
            select(FleetDocument).where(FleetDocument.id == doc_id)
        )
        return result.scalar_one_or_none()

    async def list_by_business(self, business_id: UUID) -> list[FleetDocument]:
        result = await self.session.execute(
            select(FleetDocument).where(FleetDocument.business_id == business_id)
        )
        return list(result.scalars().all())

    async def list_by_application(self, application_id: UUID) -> list[FleetDocument]:
        result = await self.session.execute(
            select(FleetDocument).where(FleetDocument.application_id == application_id)
        )
        return list(result.scalars().all())

    async def update(self, doc_id: UUID, **kwargs) -> None:
        doc = await self.get_by_id(doc_id)
        if doc:
            for key, value in kwargs.items():
                setattr(doc, key, value)
            await self.session.flush()
