from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact_message import ContactMessage


class ContactMessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, msg: ContactMessage) -> ContactMessage:
        self.session.add(msg)
        await self.session.flush()
        await self.session.refresh(msg)
        return msg
