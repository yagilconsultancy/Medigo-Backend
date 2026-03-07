import logging
from uuid import UUID

from app.config import settings
from app.models.location_history import LocationHistory
from app.models.tracking_session import TrackingSession
from app.repositories.location_history_repo import LocationHistoryRepository
from app.repositories.tracking_session_repo import TrackingSessionRepository
from app.services.location_service_client import LocationServiceClient
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher
from mediride_common.events.schemas import DriverLocationUpdatedPayload, RideETAUpdatedPayload
from mediride_common.exceptions import NotFoundError
from mediride_common.utils import utc_now

logger = logging.getLogger(__name__)


class TrackingService:
    def __init__(
        self,
        session_repo: TrackingSessionRepository,
        history_repo: LocationHistoryRepository,
        publisher: EventPublisher,
    ):
        self.session_repo = session_repo
        self.history_repo = history_repo
        self.publisher = publisher
        self.location_client = LocationServiceClient(settings.LOCATION_SERVICE_URL)

    async def start_session(
        self,
        ride_id: UUID,
        driver_id: UUID,
        rider_id: UUID,
        pickup_latitude: float,
        pickup_longitude: float,
        destination_latitude: float,
        destination_longitude: float,
    ) -> TrackingSession:
        existing = await self.session_repo.get_active_by_ride_id(ride_id)
        if existing:
            logger.info(f"Tracking session already exists for ride {ride_id}")
            return existing

        session = TrackingSession(
            ride_id=ride_id,
            driver_id=driver_id,
            rider_id=rider_id,
            status="active",
            pickup_latitude=pickup_latitude,
            pickup_longitude=pickup_longitude,
            destination_latitude=destination_latitude,
            destination_longitude=destination_longitude,
        )
        session = await self.session_repo.create(session)
        logger.info(f"Tracking session started for ride {ride_id}")
        return session

    async def update_location(
        self,
        driver_id: UUID,
        latitude: float,
        longitude: float,
        heading: float | None = None,
        speed: float | None = None,
    ) -> dict | None:
        session = await self.session_repo.get_active_by_driver_id(driver_id)
        if not session:
            return None

        # Store location history
        entry = LocationHistory(
            session_id=session.id,
            driver_id=driver_id,
            latitude=latitude,
            longitude=longitude,
            heading=heading,
            speed=speed,
        )
        await self.history_repo.create(entry)

        # Calculate ETA from driver's current position to destination
        eta_minutes = None
        distance_miles = None
        distance_data = await self.location_client.calculate_distance(
            latitude, longitude,
            float(session.destination_latitude), float(session.destination_longitude),
        )
        if distance_data:
            eta_minutes = distance_data.get("duration_minutes")
            distance_miles = distance_data.get("distance_miles")

        # Update session with current position and ETA
        await self.session_repo.update_location(
            session_id=session.id,
            latitude=latitude,
            longitude=longitude,
            heading=heading,
            speed=speed,
            eta_minutes=eta_minutes,
            distance_remaining_miles=distance_miles,
        )

        # Publish location update event
        await self.publisher.publish(
            Exchanges.TRACKING,
            RoutingKeys.DRIVER_LOCATION_UPDATED,
            DriverLocationUpdatedPayload(
                driver_id=driver_id,
                ride_id=session.ride_id,
                latitude=latitude,
                longitude=longitude,
                heading=heading,
                speed=speed,
            ).model_dump(mode="json"),
        )

        # Publish ETA update if available
        if eta_minutes is not None:
            await self.publisher.publish(
                Exchanges.TRACKING,
                RoutingKeys.RIDE_ETA_UPDATED,
                RideETAUpdatedPayload(
                    ride_id=session.ride_id,
                    rider_id=session.rider_id,
                    driver_id=driver_id,
                    eta_minutes=eta_minutes,
                    distance_miles=distance_miles or 0,
                ).model_dump(mode="json"),
            )

        return {
            "ride_id": str(session.ride_id),
            "driver_id": str(driver_id),
            "latitude": latitude,
            "longitude": longitude,
            "heading": heading,
            "speed": speed,
            "eta_minutes": eta_minutes,
            "distance_remaining_miles": distance_miles,
        }

    async def get_session(self, ride_id: UUID) -> TrackingSession:
        session = await self.session_repo.get_active_by_ride_id(ride_id)
        if not session:
            raise NotFoundError("No active tracking session for this ride")
        return session

    async def get_session_by_driver(self, driver_id: UUID) -> TrackingSession:
        session = await self.session_repo.get_active_by_driver_id(driver_id)
        if not session:
            raise NotFoundError("No active tracking session for this driver")
        return session

    async def end_session(self, ride_id: UUID) -> None:
        session = await self.session_repo.get_active_by_ride_id(ride_id)
        if not session:
            logger.warning(f"No active tracking session to end for ride {ride_id}")
            return
        await self.session_repo.end_session(session.id)
        logger.info(f"Tracking session ended for ride {ride_id}")

    async def get_location_history(
        self, ride_id: UUID, offset: int = 0, limit: int = 1000
    ) -> tuple[list[LocationHistory], int, UUID]:
        session = await self.session_repo.get_active_by_ride_id(ride_id)
        if not session:
            # Try completed sessions
            from sqlalchemy import select
            raise NotFoundError("No tracking session found for this ride")

        entries, total = await self.history_repo.get_by_session(session.id, offset, limit)
        return entries, total, session.id
