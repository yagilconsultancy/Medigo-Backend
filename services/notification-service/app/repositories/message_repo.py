from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message


class MessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, message: Message) -> Message:
        self.session.add(message)
        await self.session.flush()
        await self.session.refresh(message)
        return message

    async def get_by_id(self, message_id: UUID) -> Message | None:
        result = await self.session.execute(
            select(Message).where(Message.id == message_id)
        )
        return result.scalar_one_or_none()

    async def get_by_conversation(
        self, conversation_id: UUID, offset: int = 0, limit: int = 50
    ) -> tuple[list[Message], int]:
        query = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(query)
        messages = list(result.scalars().all())

        count_result = await self.session.execute(
            select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
        )
        total = count_result.scalar() or 0

        return messages, total

    async def mark_as_read(self, conversation_id: UUID, user_id: UUID) -> int:
        """Mark all unread messages in conversation as read (except those sent by user)."""
        result = await self.session.execute(
            update(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.sender_id != user_id,
                Message.is_read == False,
            )
            .values(is_read=True)
        )
        return result.rowcount

    async def get_unread_count(self, conversation_id: UUID, user_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count(Message.id)).where(
                Message.conversation_id == conversation_id,
                Message.sender_id != user_id,
                Message.is_read == False,
            )
        )
        return result.scalar() or 0
