from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    message_type: str = "text"


class AddReactionRequest(BaseModel):
    emoji: str = Field(..., min_length=1, max_length=10)


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    sender_id: UUID
    content: str
    message_type: str
    is_read: bool
    created_at: datetime
    reactions: list["ReactionResponse"] = []

    model_config = {"from_attributes": True}


class ReactionResponse(BaseModel):
    id: UUID
    message_id: UUID
    user_id: UUID
    emoji: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: UUID
    ride_id: UUID
    driver_id: UUID
    rider_id: UUID
    is_active: bool
    last_message_at: datetime | None = None
    created_at: datetime
    unread_count: int = 0
    last_message: MessageResponse | None = None

    model_config = {"from_attributes": True}


MessageResponse.model_rebuild()
