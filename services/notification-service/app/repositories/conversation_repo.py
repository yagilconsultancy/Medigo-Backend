from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from mediride_common.utils import utc_now


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, conversation: Conversation) -> Conversation:
        self.session.add(conversation)
        await self.session.flush()
        await self.session.refresh(conversation)
        return conversation

    async def get_by_id(self, conv_id: UUID) -> Conversation | None:
        result = await self.session.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )
        return result.scalar_one_or_none()

    async def get_by_ride_id(self, ride_id: UUID) -> Conversation | None:
        result = await self.session.execute(
            select(Conversation).where(Conversation.ride_id == ride_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: UUID, offset: int = 0, limit: int = 20) -> tuple[list[Conversation], int]:
        # Get conversations where user is driver or rider
        query = (
            select(Conversation)
            .where(
                (Conversation.driver_id == user_id) | (Conversation.rider_id == user_id)
            )
            .where(Conversation.is_active == True)
            .order_by(Conversation.last_message_at.desc().nullslast())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(query)
        conversations = list(result.scalars().all())

        # Count
        count_query = (
            select(Conversation.id)
            .where(
                (Conversation.driver_id == user_id) | (Conversation.rider_id == user_id)
            )
            .where(Conversation.is_active == True)
        )
        count_result = await self.session.execute(count_query)
        total = len(count_result.all())

        return conversations, total

    async def update_last_message(self, conv_id: UUID) -> None:
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conv_id)
            .values(last_message_at=utc_now())
        )
