import logging

import jwt
import socketio

from app.config import settings

logger = logging.getLogger(__name__)

# Create Socket.IO server with Redis adapter for horizontal scaling.
redis_manager = socketio.AsyncRedisManager(settings.REDIS_URL)
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    client_manager=redis_manager,
    namespaces=["/chat"],
    logger=logger,
)


def _extract_user_from_auth(auth: dict | None) -> dict | None:
    """Extract user claims from Socket.IO auth token."""
    if not auth or "token" not in auth:
        return None
    try:
        payload = jwt.decode(
            auth["token"],
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type", "access") != "access":
            return None
        return {
            "user_id": payload.get("sub"),
            "role": payload.get("role"),
            "email": payload.get("email"),
        }
    except jwt.PyJWTError as e:
        logger.warning(f"Socket.IO auth failed: {e}")
        return None


@sio.on("connect", namespace="/chat")
async def on_connect(sid, environ, auth=None):
    user = _extract_user_from_auth(auth)
    if not user:
        logger.warning(f"Unauthorized chat connection attempt: {sid}")
        raise socketio.exceptions.ConnectionRefusedError("Authentication required")

    await sio.save_session(sid, user, namespace="/chat")
    logger.info(f"Chat connected: {sid} (user={user['user_id']})")


@sio.on("disconnect", namespace="/chat")
async def on_disconnect(sid):
    logger.info(f"Chat disconnected: {sid}")


async def _is_participant(user: dict, conversation_id: str) -> bool:
    """Only the ride's rider and driver (or an admin) may join its chat."""
    if user.get("role") == "admin":
        return True

    from uuid import UUID

    from app.dependencies import get_db
    from app.repositories.conversation_repo import ConversationRepository

    try:
        conv_id = UUID(str(conversation_id))
    except ValueError:
        return False

    conversation = None
    async for db_session in get_db():
        conversation = await ConversationRepository(db_session).get_by_id(conv_id)
    if not conversation:
        return False
    user_id = str(user.get("user_id"))
    return user_id in (str(conversation.rider_id), str(conversation.driver_id))


@sio.on("join_conversation", namespace="/chat")
async def on_join_conversation(sid, data):
    """Join a conversation room to receive real-time messages."""
    session = await sio.get_session(sid, namespace="/chat")
    conversation_id = data.get("conversation_id")
    if not conversation_id:
        return {"error": "conversation_id is required"}

    if not await _is_participant(session, conversation_id):
        logger.warning(f"User {session['user_id']} refused chat room for {conversation_id}")
        return {"error": "Not allowed to join this conversation"}

    room = f"chat_{conversation_id}"
    await sio.enter_room(sid, room, namespace="/chat")
    logger.info(f"User {session['user_id']} joined chat room {room}")
    return {"status": "joined", "room": room}


@sio.on("leave_conversation", namespace="/chat")
async def on_leave_conversation(sid, data):
    """Leave a conversation room."""
    conversation_id = data.get("conversation_id")
    if conversation_id:
        room = f"chat_{conversation_id}"
        await sio.leave_room(sid, room, namespace="/chat")


@sio.on("send_message", namespace="/chat")
async def on_send_message(sid, data):
    """Send a chat message via Socket.IO (real-time path)."""
    session = await sio.get_session(sid, namespace="/chat")
    conversation_id = data.get("conversation_id")
    content = data.get("content")
    message_type = data.get("message_type", "text")

    if not conversation_id or not content:
        return {"error": "conversation_id and content are required"}

    try:
        from uuid import UUID

        from app.dependencies import get_db
        from app.repositories.conversation_repo import ConversationRepository
        from app.repositories.message_repo import MessageRepository
        from app.repositories.reaction_repo import ReactionRepository
        from app.services.chat_service import ChatService

        sender_id = UUID(session["user_id"])

        async for db_session in get_db():
            service = ChatService(
                conv_repo=ConversationRepository(db_session),
                msg_repo=MessageRepository(db_session),
                reaction_repo=ReactionRepository(db_session),
            )
            message = await service.send_message(
                conversation_id=UUID(conversation_id),
                sender_id=sender_id,
                content=content,
                message_type=message_type,
            )

        # Broadcast to conversation room
        room = f"chat_{conversation_id}"
        msg_data = {
            "conversation_id": conversation_id,
            "message_id": str(message.id),
            "sender_id": str(message.sender_id),
            "content": message.content,
            "message_type": message.message_type,
            "created_at": message.created_at.isoformat(),
        }
        await sio.emit(
            "new_message",
            msg_data,
            room=room,
            namespace="/chat",
            skip_sid=sid,
        )
        return {"status": "sent", "message_id": str(message.id)}
    except Exception as e:
        logger.error(f"Error sending message via Socket.IO: {e}")
        return {"error": "Failed to send message"}


@sio.on("mark_read", namespace="/chat")
async def on_mark_read(sid, data):
    """Mark messages as read and notify the other party."""
    session = await sio.get_session(sid, namespace="/chat")
    conversation_id = data.get("conversation_id")

    if not conversation_id:
        return {"error": "conversation_id is required"}

    try:
        from uuid import UUID

        from app.dependencies import get_db
        from app.repositories.conversation_repo import ConversationRepository
        from app.repositories.message_repo import MessageRepository
        from app.repositories.reaction_repo import ReactionRepository
        from app.services.chat_service import ChatService

        user_id = UUID(session["user_id"])

        async for db_session in get_db():
            service = ChatService(
                conv_repo=ConversationRepository(db_session),
                msg_repo=MessageRepository(db_session),
                reaction_repo=ReactionRepository(db_session),
            )
            count = await service.mark_as_read(UUID(conversation_id), user_id)

        room = f"chat_{conversation_id}"
        await sio.emit(
            "messages_read",
            {"conversation_id": conversation_id, "reader_id": str(user_id), "count": count},
            room=room,
            namespace="/chat",
            skip_sid=sid,
        )
        return {"status": "ok", "messages_read": count}
    except Exception as e:
        logger.error(f"Error marking messages read: {e}")
        return {"error": "Failed to mark messages read"}


@sio.on("typing", namespace="/chat")
async def on_typing(sid, data):
    """Broadcast typing indicator (no persistence)."""
    session = await sio.get_session(sid, namespace="/chat")
    conversation_id = data.get("conversation_id")
    is_typing = data.get("is_typing", True)

    if conversation_id:
        room = f"chat_{conversation_id}"
        await sio.emit(
            "typing",
            {
                "conversation_id": conversation_id,
                "user_id": session["user_id"],
                "is_typing": is_typing,
            },
            room=room,
            namespace="/chat",
            skip_sid=sid,
        )


async def emit_new_message(conversation_id: str, message_data: dict) -> None:
    """Utility to emit a new message from outside Socket.IO handlers (e.g., from REST API)."""
    room = f"chat_{conversation_id}"
    await sio.emit("new_message", message_data, room=room, namespace="/chat")
