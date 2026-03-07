from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.reaction_repo import ReactionRepository
from app.schemas.chat import (
    AddReactionRequest,
    ConversationResponse,
    MessageResponse,
    ReactionResponse,
    SendMessageRequest,
)
from app.services.chat_service import ChatService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import PaginatedResponse, StandardResponse

router = APIRouter()


def _get_chat_service(session: AsyncSession = Depends(get_db)) -> ChatService:
    return ChatService(
        conv_repo=ConversationRepository(session),
        msg_repo=MessageRepository(session),
        reaction_repo=ReactionRepository(session),
    )


@router.get("/chats", response_model=PaginatedResponse[ConversationResponse])
async def list_conversations(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.DRIVER, UserRole.RIDER])),
    service: ChatService = Depends(_get_chat_service),
):
    offset = (page - 1) * limit
    enriched_list, total = await service.get_conversations(user.id, offset, limit)

    data = []
    for item in enriched_list:
        conv = item["conversation"]
        last_msg = item["last_message"]
        data.append(ConversationResponse(
            id=conv.id,
            ride_id=conv.ride_id,
            driver_id=conv.driver_id,
            rider_id=conv.rider_id,
            is_active=conv.is_active,
            last_message_at=conv.last_message_at,
            created_at=conv.created_at,
            unread_count=item["unread_count"],
            last_message=MessageResponse.model_validate(last_msg) if last_msg else None,
        ))

    return PaginatedResponse(
        data=data,
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.get("/chats/{conversation_id}/messages", response_model=PaginatedResponse[MessageResponse])
async def get_messages(
    conversation_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.DRIVER, UserRole.RIDER])),
    service: ChatService = Depends(_get_chat_service),
):
    offset = (page - 1) * limit
    messages, total = await service.get_messages(conversation_id, user.id, offset, limit)
    return PaginatedResponse(
        data=[MessageResponse.model_validate(m) for m in messages],
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.post("/chats/{conversation_id}/messages", response_model=StandardResponse[MessageResponse])
async def send_message(
    conversation_id: UUID,
    body: SendMessageRequest,
    user: UserClaims = Depends(require_role([UserRole.DRIVER, UserRole.RIDER])),
    service: ChatService = Depends(_get_chat_service),
):
    message = await service.send_message(
        conversation_id=conversation_id,
        sender_id=user.id,
        content=body.content,
        message_type=body.message_type,
    )
    return StandardResponse(
        data=MessageResponse.model_validate(message),
        message="Message sent",
    )


@router.put("/chats/{conversation_id}/read", response_model=StandardResponse[dict])
async def mark_messages_read(
    conversation_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.DRIVER, UserRole.RIDER])),
    service: ChatService = Depends(_get_chat_service),
):
    count = await service.mark_as_read(conversation_id, user.id)
    return StandardResponse(
        data={"messages_read": count},
        message="Messages marked as read",
    )


@router.post(
    "/chats/{conversation_id}/messages/{message_id}/reaction",
    response_model=StandardResponse[ReactionResponse],
)
async def add_reaction(
    conversation_id: UUID,
    message_id: UUID,
    body: AddReactionRequest,
    user: UserClaims = Depends(require_role([UserRole.DRIVER, UserRole.RIDER])),
    service: ChatService = Depends(_get_chat_service),
):
    reaction = await service.add_reaction(message_id, user.id, body.emoji)
    return StandardResponse(
        data=ReactionResponse.model_validate(reaction),
        message="Reaction added",
    )
