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
        if payload.get("type", "access") != "access":
            return None
        return {
            "user_id": payload.get("sub"),
            "role": payload.get("role"),
            "email": payload.get("email"),
            "business_id": payload.get("business_id"),
        }
    except jwt.PyJWTError as e:
        logger.warning(f"Socket.IO auth failed: {e}")
        return None


def _guest_session_from_auth(auth: dict | None) -> str | None:
    """Guest riders have no login token; they identify with their booking session id."""
    if not auth:
        return None
    value = auth.get("guest_session_id")
    if not value:
        return None
    from uuid import UUID

    try:
        return str(UUID(str(value)))
    except ValueError:
        return None


@sio.on("connect", namespace="/tracking")
async def on_connect(sid, environ, auth=None):
    user = _extract_user_from_auth(auth)
    if not user:
        guest_session_id = _guest_session_from_auth(auth)
        if guest_session_id:
            user = {
                "user_id": f"guest_{guest_session_id}",
                "role": "guest",
                "email": None,
                "guest_session_id": guest_session_id,
            }
            await sio.save_session(sid, user, namespace="/tracking")
            logger.info(f"Guest Socket.IO connection: {sid}")
            return
        if settings.ENVIRONMENT != "development":
            logger.warning(f"Unauthenticated tracking connection refused: {sid}")
            raise socketio.exceptions.ConnectionRefusedError("Authentication required")
        user = {"user_id": f"guest_{sid}", "role": "guest", "email": None}
        logger.info(f"Guest Socket.IO connection (development): {sid}")
    else:
        logger.info(f"Socket.IO connected: {sid} (user={user['user_id']}, role={user['role']})")

    await sio.save_session(sid, user, namespace="/tracking")


async def _can_watch_ride(user: dict, ride_id: str) -> bool:
    """Admins see every ride; everyone else only rides they take part in."""
    if user.get("role") == "admin":
        return True
    if settings.ENVIRONMENT == "development" and user.get("role") == "guest" and not user.get("guest_session_id"):
        return True

    from uuid import UUID

    from app.clients.ride_service_client import RideServiceClient

    try:
        ride = await RideServiceClient(settings.RIDE_SERVICE_URL).get_ride(UUID(str(ride_id)))
    except ValueError:
        return False
    if not ride:
        return False

    if user.get("role") == "guest":
        guest_session_id = user.get("guest_session_id")
        return bool(guest_session_id) and str(ride.get("guest_session_id")) == guest_session_id

    user_id = str(user.get("user_id"))
    participants = {str(ride.get(k)) for k in ("rider_id", "driver_id", "caregiver_id") if ride.get(k)}
    if user_id in participants:
        return True
    business_id = user.get("business_id")
    return bool(business_id) and str(ride.get("business_id")) == str(business_id)


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

    if not await _can_watch_ride(session, ride_id):
        logger.warning(f"User {session['user_id']} refused tracking room for ride {ride_id}")
        return {"error": "Not allowed to track this ride"}

    room = f"ride_{ride_id}"
    await sio.enter_room(sid, room, namespace="/tracking")
    logger.info(f"User {session['user_id']} joined tracking room {room}")
    return {"status": "joined", "room": room}


@sio.on("leave_ride", namespace="/tracking")
async def on_leave_ride(sid, data):
    """Leave a ride tracking room."""
    ride_id = data.get("ride_id")
    if ride_id:
        room = f"ride_{ride_id}"
        await sio.leave_room(sid, room, namespace="/tracking")
        logger.info(f"SID {sid} left tracking room {room}")


@sio.on("join_dispatch_center", namespace="/tracking")
async def on_join_dispatch_center(sid):
    """Admin joins dispatch center room to receive all active trip location updates."""
    session = await sio.get_session(sid, namespace="/tracking")
    if session.get("role") != "admin":
        return {"error": "Only admins can join dispatch center"}

    room = "dispatch_center"
    await sio.enter_room(sid, room, namespace="/tracking")
    logger.info(f"Admin {session['user_id']} joined dispatch center room")
    return {"status": "joined", "room": room}


@sio.on("leave_dispatch_center", namespace="/tracking")
async def on_leave_dispatch_center(sid):
    """Leave dispatch center room."""
    room = "dispatch_center"
    await sio.leave_room(sid, room, namespace="/tracking")
    logger.info(f"SID {sid} left dispatch center room")


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
            # Broadcast to specific ride room
            ride_room = f"ride_{result['ride_id']}"
            try:
                room_sids = list(sio.manager.get_participants("/tracking", ride_room))
                logger.info(
                    "Broadcasting location_update to room=%s skip_sid=%s room_members=%s",
                    ride_room, sid, [s for s, _ in room_sids],
                )
            except Exception as dbg_err:
                logger.warning("Could not list room members: %s", dbg_err)
            await sio.emit(
                "location_update",
                result,
                room=ride_room,
                namespace="/tracking",
                skip_sid=sid,
            )
            logger.info("location_update emitted to room=%s", ride_room)

            # Also broadcast to dispatch center room for live map
            await sio.emit(
                "dispatch_location_update",
                result,
                room="dispatch_center",
                namespace="/tracking",
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
