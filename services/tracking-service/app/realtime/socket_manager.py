import logging

import jwt
import socketio

from app.config import settings

logger = logging.getLogger(__name__)

# Create Socket.IO server with Redis adapter for horizontal scaling
redis_manager = socketio.AsyncRedisManager(settings.REDIS_URL)
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    client_manager=redis_manager,
    namespaces=["/tracking"],
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
        return {
            "user_id": payload.get("sub"),
            "role": payload.get("role"),
            "email": payload.get("email"),
        }
    except jwt.PyJWTError as e:
        logger.warning(f"Socket.IO auth failed: {e}")
        return None


@sio.on("connect", namespace="/tracking")
async def on_connect(sid, environ, auth=None):
    user = _extract_user_from_auth(auth)
    if not user:
        logger.warning(f"Unauthorized Socket.IO connection attempt: {sid}")
        raise socketio.exceptions.ConnectionRefusedError("Authentication required")

    await sio.save_session(sid, user, namespace="/tracking")
    logger.info(f"Socket.IO connected: {sid} (user={user['user_id']}, role={user['role']})")


@sio.on("disconnect", namespace="/tracking")
async def on_disconnect(sid):
    logger.info(f"Socket.IO disconnected: {sid}")


@sio.on("join_ride", namespace="/tracking")
async def on_join_ride(sid, data):
    """Rider or driver joins a ride room to receive/send location updates."""
    session = await sio.get_session(sid, namespace="/tracking")
    ride_id = data.get("ride_id")
    if not ride_id:
        return {"error": "ride_id is required"}

    room = f"ride_{ride_id}"
    sio.enter_room(sid, room, namespace="/tracking")
    logger.info(f"User {session['user_id']} joined tracking room {room}")
    return {"status": "joined", "room": room}


@sio.on("leave_ride", namespace="/tracking")
async def on_leave_ride(sid, data):
    """Leave a ride tracking room."""
    ride_id = data.get("ride_id")
    if ride_id:
        room = f"ride_{ride_id}"
        sio.leave_room(sid, room, namespace="/tracking")
        logger.info(f"SID {sid} left tracking room {room}")


@sio.on("update_location", namespace="/tracking")
async def on_update_location(sid, data):
    """Driver pushes GPS location update. Broadcasts to ride room."""
    session = await sio.get_session(sid, namespace="/tracking")
    if session.get("role") != "driver":
        return {"error": "Only drivers can send location updates"}

    # Import here to avoid circular imports at module level
    from app.dependencies import get_db, get_publisher
    from app.repositories.location_history_repo import LocationHistoryRepository
    from app.repositories.tracking_session_repo import TrackingSessionRepository
    from app.services.tracking_service import TrackingService

    latitude = data.get("latitude")
    longitude = data.get("longitude")
    heading = data.get("heading")
    speed = data.get("speed")

    if latitude is None or longitude is None:
        return {"error": "latitude and longitude are required"}

    try:
        from uuid import UUID
        driver_id = UUID(session["user_id"])

        async for db_session in get_db():
            publisher = get_publisher()
            service = TrackingService(
                session_repo=TrackingSessionRepository(db_session),
                history_repo=LocationHistoryRepository(db_session),
                publisher=publisher,
            )
            result = service_result = await service.update_location(
                driver_id=driver_id,
                latitude=latitude,
                longitude=longitude,
                heading=heading,
                speed=speed,
            )

        if result:
            room = f"ride_{result['ride_id']}"
            await sio.emit(
                "location_update",
                result,
                room=room,
                namespace="/tracking",
                skip_sid=sid,
            )
            return {"status": "ok"}
        return {"error": "No active tracking session"}
    except Exception as e:
        logger.error(f"Error updating location: {e}")
        return {"error": "Failed to update location"}


async def emit_tracking_started(ride_id: str, driver_id: str) -> None:
    """Notify room that tracking has started."""
    room = f"ride_{ride_id}"
    await sio.emit(
        "tracking_started",
        {"ride_id": ride_id, "driver_id": driver_id},
        room=room,
        namespace="/tracking",
    )


async def emit_tracking_ended(ride_id: str, reason: str) -> None:
    """Notify room that tracking has ended."""
    room = f"ride_{ride_id}"
    await sio.emit(
        "tracking_ended",
        {"ride_id": ride_id, "reason": reason},
        room=room,
        namespace="/tracking",
    )
