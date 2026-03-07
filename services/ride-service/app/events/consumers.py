import logging

from app.dependencies import get_broker, get_db, get_publisher
from app.repositories.ride_repo import RideRepository
from mediride_common.events.constants import Exchanges, Queues, RoutingKeys
from mediride_common.events.consumer import BaseEventConsumer
from mediride_common.events.schemas import DriverStatusPayload, EventEnvelope, PaymentCompletedPayload

logger = logging.getLogger(__name__)


class DriverStatusConsumer(BaseEventConsumer):
    """Consumes driver online/offline events to track available drivers."""

    async def handle(self, envelope: EventEnvelope) -> None:
        if envelope.event_type not in (RoutingKeys.DRIVER_ONLINE, RoutingKeys.DRIVER_OFFLINE):
            return

        payload = DriverStatusPayload(**envelope.payload)
        is_online = envelope.event_type == RoutingKeys.DRIVER_ONLINE
        logger.info(
            f"Driver {payload.driver_id} is now {'online' if is_online else 'offline'}"
        )


class PaymentEventConsumer(BaseEventConsumer):
    """Consumes payment events to update ride fare."""

    async def handle(self, envelope: EventEnvelope) -> None:
        if envelope.event_type != RoutingKeys.PAYMENT_COMPLETED:
            return

        payload = PaymentCompletedPayload(**envelope.payload)
        logger.info(f"Payment completed for ride {payload.ride_id}: ${payload.amount}")

        async for session in get_db():
            repo = RideRepository(session)
            ride = await repo.get_by_id(payload.ride_id)
            if ride:
                await repo.update(payload.ride_id, final_fare=payload.amount)
                logger.info(f"Updated ride {payload.ride_id} fare to ${payload.amount}")


async def setup_consumers() -> None:
    broker = get_broker()
    if not broker:
        logger.warning("Broker not available, skipping consumer setup")
        return

    # Driver status consumer
    driver_status_consumer = DriverStatusConsumer(broker)
    await driver_status_consumer.setup_queue(
        queue_name=Queues.RIDE_DRIVER_STATUS,
        exchange_name=Exchanges.USERS,
        routing_keys=[RoutingKeys.DRIVER_ONLINE, RoutingKeys.DRIVER_OFFLINE],
    )

    # Payment event consumer
    payment_consumer = PaymentEventConsumer(broker)
    await payment_consumer.setup_queue(
        queue_name=Queues.RIDE_PAYMENT_EVENTS,
        exchange_name=Exchanges.PAYMENTS,
        routing_keys=[RoutingKeys.PAYMENT_COMPLETED],
    )

    logger.info("Ride service consumers initialized")
