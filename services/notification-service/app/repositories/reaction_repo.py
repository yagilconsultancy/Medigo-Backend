from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message_reaction import MessageReaction


class ReactionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, reaction: MessageReaction) -> MessageReaction:
        self.session.add(reaction)
        await self.session.flush()
        await self.session.refresh(reaction)
        return reaction

    async def get_by_message(self, message_id: UUID) -> list[MessageReaction]:
        result = await self.session.execute(
            select(MessageReaction).where(MessageReaction.message_id == message_id)
        )
        return list(result.scalars().all())

    async def delete_reaction(self, reaction_id: UUID) -> None:
        await self.session.execute(
            delete(MessageReaction).where(MessageReaction.id == reaction_id)
        )
