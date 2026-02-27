import logging

from app.dependencies import get_broker, get_db
from app.repositories.user_repo import UserRepository
from app.services.user_service import UserService
from mediride_common.events.constants import Exchanges, Queues, RoutingKeys
from mediride_common.events.consumer import BaseEventConsumer
from mediride_common.events.schemas import EventEnvelope, UserRegisteredPayload

logger = logging.getLogger(__name__)


class UserRegisteredConsumer(BaseEventConsumer):
    """Consumes user.registered events to create user profiles."""

    async def handle(self, envelope: EventEnvelope) -> None:
        if envelope.event_type != RoutingKeys.USER_REGISTERED:
            return

        payload = UserRegisteredPayload(**envelope.payload)
        logger.info(f"Creating profile for user {payload.user_id}")

        # Get a database session
        async for session in get_db():
            user_repo = UserRepository(session)
            user_service = UserService(user_repo)

            # Check if profile already exists (idempotency)
            existing = await user_repo.get_by_id(payload.user_id)
            if existing:
                logger.info(f"Profile already exists for user {payload.user_id}")
                return

            await user_service.create_profile_from_registration(
                user_id=payload.user_id,
                email=payload.email,
                phone=payload.phone,
                role=payload.role,
                business_id=payload.business_id,
            )
            logger.info(f"Profile created for user {payload.user_id}")


async def setup_consumers() -> None:
    """Set up all event consumers for the user service."""
    broker = get_broker()
    if not broker:
        logger.warning("Broker not available, skipping consumer setup")
        return

    consumer = UserRegisteredConsumer(broker)
    await consumer.setup_queue(
        queue_name=Queues.USER_SERVICE_USER_REGISTERED,
        exchange_name=Exchanges.AUTH,
        routing_keys=[RoutingKeys.USER_REGISTERED],
    )
    logger.info("User service consumers initialized")
