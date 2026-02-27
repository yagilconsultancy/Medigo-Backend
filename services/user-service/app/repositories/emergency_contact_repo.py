from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.emergency_contact import EmergencyContact


class EmergencyContactRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, contact: EmergencyContact) -> EmergencyContact:
        self.session.add(contact)
        await self.session.flush()
        return contact

    async def get_by_id(self, contact_id: UUID) -> EmergencyContact | None:
        return await self.session.get(EmergencyContact, contact_id)

    async def list_by_user(self, user_id: UUID) -> list[EmergencyContact]:
        result = await self.session.execute(
            select(EmergencyContact)
            .where(EmergencyContact.user_id == user_id)
            .order_by(EmergencyContact.is_primary.desc())
        )
        return list(result.scalars().all())

    async def update(self, contact_id: UUID, **kwargs) -> None:
        await self.session.execute(
            update(EmergencyContact)
            .where(EmergencyContact.id == contact_id)
            .values(**kwargs)
        )

    async def delete(self, contact_id: UUID) -> None:
        await self.session.execute(
            delete(EmergencyContact).where(EmergencyContact.id == contact_id)
        )
