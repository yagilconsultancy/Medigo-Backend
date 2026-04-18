import logging

from app.dependencies import get_broker, get_db, get_publisher
from app.repositories.location_history_repo import LocationHistoryRepository
from app.repositories.tracking_session_repo import TrackingSessionRepository
from app.services.tracking_service import TrackingService
from mediride_common.events.constants import Exchanges, Queues, RoutingKeys
from mediride_common.events.consumer import BaseEventConsumer
from mediride_common.events.schemas import EventEnvelope, RideStatusChangedPayload

logger = logging.getLogger(__name__)

# Ride statuses that need tracking
TRACKING_START_STATUSES = {RoutingKeys.RIDE_DRIVER_ASSIGNED, RoutingKeys.RIDE_DRIVER_EN_ROUTE}
TRACKING_END_STATUSES = {RoutingKeys.RIDE_COMPLETED, RoutingKeys.RIDE_CANCELLED, RoutingKeys.RIDE_NO_SHOW}


class RideLifecycleConsumer(BaseEventConsumer):
    """Consumes ride lifecycle events to manage tracking sessions."""

    async def handle(self, envelope: EventEnvelope) -> None:
        event_type = envelope.event_type

        if event_type in TRACKING_START_STATUSES:
            await self._handle_tracking_start(envelope)
        elif event_type in TRACKING_END_STATUSES:
            await self._handle_tracking_end(envelope)
        elif event_type == RoutingKeys.RIDE_DRIVER_ARRIVED:
            logger.info(f"Driver arrived for ride - tracking continues")

    async def _handle_tracking_start(self, envelope: EventEnvelope) -> None:
        payload = RideStatusChangedPayload(**envelope.payload)
        logger.info(f"Starting tracking for ride {payload.ride_id}")

        async for session in get_db():
            publisher = get_publisher()
            service = TrackingService(
                session_repo=TrackingSessionRepository(session),
                history_repo=LocationHistoryRepository(session),
                publisher=publisher,
            )

            # We need the ride details for pickup/destination coordinates
            # For now, create with placeholder coords - will be updated on first location update
            # In production, we'd fetch ride details from ride-service
            try:
                tracking_session = await service.start_session(
                    ride_id=payload.ride_id,
                    driver_id=payload.driver_id,
                    rider_id=payload.rider_id,
                    pickup_latitude=0.0,
                    pickup_longitude=0.0,
                    destination_latitude=0.0,
                    destination_longitude=0.0,
                )
                logger.info(f"Tracking session created: {tracking_session.id}")

                # Emit Socket.IO event
                from app.realtime.socket_manager import emit_tracking_started
                await emit_tracking_started(
                    str(payload.ride_id), str(payload.driver_id)
                )
            except Exception as e:
                logger.error(f"Failed to start tracking for ride {payload.ride_id}: {e}")

    async def _handle_tracking_end(self, envelope: EventEnvelope) -> None:
        payload = RideStatusChangedPayload(**envelope.payload)
        logger.info(f"Ending tracking for ride {payload.ride_id} (status={payload.to_status})")

        async for session in get_db():
            publisher = get_publisher()
            service = TrackingService(
                session_repo=TrackingSessionRepository(session),
                history_repo=LocationHistoryRepository(session),
                publisher=publisher,
            )
            await service.end_session(payload.ride_id)

            # Emit Socket.IO event
            from app.realtime.socket_manager import emit_tracking_ended
            await emit_tracking_ended(str(payload.ride_id), payload.to_status)


async def setup_consumers() -> None:
    broker = get_broker()
    if not broker:
        logger.warning("Broker not available, skipping consumer setup")
        return

    ride_lifecycle_consumer = RideLifecycleConsumer(broker)
    await ride_lifecycle_consumer.setup_queue(
        queue_name=Queues.TRACKING_RIDE_LIFECYCLE,
        exchange_name=Exchanges.RIDES,
        routing_keys=[
            RoutingKeys.RIDE_DRIVER_ASSIGNED,
            RoutingKeys.RIDE_DRIVER_EN_ROUTE,
            RoutingKeys.RIDE_DRIVER_ARRIVED,
            RoutingKeys.RIDE_COMPLETED,
            RoutingKeys.RIDE_CANCELLED,
            RoutingKeys.RIDE_NO_SHOW,
        ],
    )

    logger.info("Tracking service consumers initialized")
