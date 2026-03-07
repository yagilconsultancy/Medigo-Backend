import logging
from uuid import UUID

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.message_reaction import MessageReaction
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.reaction_repo import ReactionRepository
from mediride_common.exceptions import NotFoundError, AuthorizationError

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        conv_repo: ConversationRepository,
        msg_repo: MessageRepository,
        reaction_repo: ReactionRepository,
    ):
        self.conv_repo = conv_repo
        self.msg_repo = msg_repo
        self.reaction_repo = reaction_repo

    async def get_or_create_conversation(
        self, ride_id: UUID, driver_id: UUID, rider_id: UUID
    ) -> Conversation:
        conv = await self.conv_repo.get_by_ride_id(ride_id)
        if conv:
            return conv

        conv = Conversation(
            ride_id=ride_id,
            driver_id=driver_id,
            rider_id=rider_id,
        )
        return await self.conv_repo.create(conv)

    async def get_conversations(
        self, user_id: UUID, offset: int = 0, limit: int = 20
    ) -> tuple[list[dict], int]:
        conversations, total = await self.conv_repo.get_by_user(user_id, offset, limit)

        enriched = []
        for conv in conversations:
            unread = await self.msg_repo.get_unread_count(conv.id, user_id)
            messages, _ = await self.msg_repo.get_by_conversation(conv.id, 0, 1)
            last_msg = messages[0] if messages else None

            enriched.append({
                "conversation": conv,
                "unread_count": unread,
                "last_message": last_msg,
            })

        return enriched, total

    async def get_messages(
        self, conversation_id: UUID, user_id: UUID, offset: int = 0, limit: int = 50
    ) -> tuple[list[Message], int]:
        conv = await self.conv_repo.get_by_id(conversation_id)
        if not conv:
            raise NotFoundError("Conversation not found")

        if user_id not in (conv.driver_id, conv.rider_id):
            raise AuthorizationError("Not a participant in this conversation")

        return await self.msg_repo.get_by_conversation(conversation_id, offset, limit)

    async def send_message(
        self, conversation_id: UUID, sender_id: UUID, content: str, message_type: str = "text"
    ) -> Message:
        conv = await self.conv_repo.get_by_id(conversation_id)
        if not conv:
            raise NotFoundError("Conversation not found")

        if sender_id not in (conv.driver_id, conv.rider_id):
            raise AuthorizationError("Not a participant in this conversation")

        message = Message(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=content,
            message_type=message_type,
        )
        message = await self.msg_repo.create(message)
        await self.conv_repo.update_last_message(conversation_id)

        logger.info(f"Message sent in conversation {conversation_id} by {sender_id}")
        return message

    async def mark_as_read(self, conversation_id: UUID, user_id: UUID) -> int:
        conv = await self.conv_repo.get_by_id(conversation_id)
        if not conv:
            raise NotFoundError("Conversation not found")

        if user_id not in (conv.driver_id, conv.rider_id):
            raise AuthorizationError("Not a participant in this conversation")

        return await self.msg_repo.mark_as_read(conversation_id, user_id)

    async def add_reaction(
        self, message_id: UUID, user_id: UUID, emoji: str
    ) -> MessageReaction:
        msg = await self.msg_repo.get_by_id(message_id)
        if not msg:
            raise NotFoundError("Message not found")

        conv = await self.conv_repo.get_by_id(msg.conversation_id)
        if not conv or user_id not in (conv.driver_id, conv.rider_id):
            raise AuthorizationError("Not a participant in this conversation")

        reaction = MessageReaction(
            message_id=message_id,
            user_id=user_id,
            emoji=emoji,
        )
        return await self.reaction_repo.create(reaction)
