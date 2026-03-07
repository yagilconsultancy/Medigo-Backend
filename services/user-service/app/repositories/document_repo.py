from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.driver_document import DriverDocument
from mediride_common.utils import utc_now


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, document: DriverDocument) -> DriverDocument:
        self.session.add(document)
        await self.session.flush()
        return document

    async def get_by_id(self, document_id: UUID) -> DriverDocument | None:
        result = await self.session.execute(
            select(DriverDocument).where(DriverDocument.id == document_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user_and_type(
        self, user_id: UUID, document_type: str
    ) -> DriverDocument | None:
        result = await self.session.execute(
            select(DriverDocument).where(
                DriverDocument.user_id == user_id,
                DriverDocument.document_type == document_type,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: UUID) -> list[DriverDocument]:
        result = await self.session.execute(
            select(DriverDocument)
            .where(DriverDocument.user_id == user_id)
            .order_by(DriverDocument.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        document_id: UUID,
        status: str,
        verified_by: UUID | None = None,
        rejection_reason: str | None = None,
    ) -> None:
        values = {"verification_status": status}
        if status == "approved":
            values["verified_at"] = utc_now()
            values["verified_by"] = verified_by
            values["rejection_reason"] = None
        elif status == "rejected":
            values["verified_by"] = verified_by
            values["rejection_reason"] = rejection_reason
        await self.session.execute(
            update(DriverDocument)
            .where(DriverDocument.id == document_id)
            .values(**values)
        )

    async def delete(self, document_id: UUID) -> None:
        document = await self.get_by_id(document_id)
        if document:
            await self.session.delete(document)
            await self.session.flush()
