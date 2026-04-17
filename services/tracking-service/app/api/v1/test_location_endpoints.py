"""
Public test endpoints for simulating driver location updates.
These endpoints bypass authentication for testing purposes.
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_publisher
from app.realtime.socket_manager import sio
from app.repositories.location_history_repo import LocationHistoryRepository
from app.repositories.tracking_session_repo import TrackingSessionRepository
from app.schemas.tracking import SimulateLocationUpdateRequest
from app.services.tracking_service import TrackingService
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_tracking_service(
    session: AsyncSession = Depends(get_db),
    publisher: EventPublisher = Depends(get_publisher),
) -> TrackingService:
    return TrackingService(
        session_repo=TrackingSessionRepository(session),
        history_repo=LocationHistoryRepository(session),
        publisher=publisher,
    )


@router.post("/simulate-location", response_model=StandardResponse[dict])
async def simulate_driver_location(
    request: SimulateLocationUpdateRequest,
    service: TrackingService = Depends(_get_tracking_service),
):
    """
    **PUBLIC ENDPOINT** - Simulate driver GPS location update for testing.

    This endpoint allows testing the real-time tracking map without requiring
    actual mobile devices with GPS. It simulates what a driver's app would send.

    **Use Case**: Testing the live map, ETA calculations, and real-time updates

    **Example**:
    ```json
    {
      "driver_id": "uuid-of-driver",
      "latitude": 43.6532,
      "longitude": -79.3832,
      "heading": 180.5,
      "speed": 45.2
    }
    ```

    **Behavior**:
    - Updates driver's current location in tracking session
    - Calculates ETA to destination
    - Publishes location event to RabbitMQ
    - Broadcasts to Socket.IO rooms (ride room + dispatch center)
    """
    try:
        # Update location using the tracking service
        result = await service.update_location(
            driver_id=request.driver_id,
            latitude=request.latitude,
            longitude=request.longitude,
            heading=request.heading,
            speed=request.speed,
        )

        if not result:
            return StandardResponse(
                success=False,
                message="No active tracking session found for this driver",
                data=None,
            )

        # Broadcast to Socket.IO rooms (same logic as real-time updates)
        ride_id = result["ride_id"]
        ride_room = f"ride_{ride_id}"

        # Emit to ride-specific room (rider + driver in that ride)
        await sio.emit(
            "location_update",
            result,
            room=ride_room,
            namespace="/tracking",
        )

        # Emit to dispatch center room (admin live map)
        await sio.emit(
            "dispatch_location_update",
            result,
            room="dispatch_center",
            namespace="/tracking",
        )

        logger.info(
            f"Simulated location update for driver {request.driver_id}: "
            f"({request.latitude}, {request.longitude}) "
            f"ETA: {result.get('eta_minutes')}min"
        )

        return StandardResponse(
            data=result,
            message="Location update simulated successfully",
        )

    except Exception as e:
        logger.error(f"Error simulating location update: {e}")
        return StandardResponse(
            success=False,
            message=f"Failed to simulate location update: {str(e)}",
            data=None,
        )
