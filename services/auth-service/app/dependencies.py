from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from mediride_common.database.base import get_async_engine, get_async_session_factory
from mediride_common.events.broker import RabbitMQBroker
from mediride_common.events.constants import Exchanges, Queues, RoutingKeys
from mediride_common.events.publisher import EventPublisher

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_broker: RabbitMQBroker | None = None
_publisher: EventPublisher | None = None


async def init_db() -> None:
    global _engine, _session_factory
    _engine = get_async_engine(settings.DATABASE_URL)
    _session_factory = get_async_session_factory(_engine)


async def init_broker() -> None:
    global _broker, _publisher
    _broker = RabbitMQBroker(settings.RABBITMQ_URL)
    await _broker.connect()
    # Pre-declare the notification queue so OTP messages are persisted
    # even if the notification service hasn't started yet.
    await _broker.ensure_queue(
        queue_name=Queues.NOTIFICATION_AUTH_EVENTS,
        exchange_name=Exchanges.AUTH,
        routing_keys=[
            RoutingKeys.USER_OTP_REQUESTED,
            RoutingKeys.USER_REGISTERED,
            RoutingKeys.USER_VERIFIED,
            RoutingKeys.DRIVER_INVITE_SENT,
            RoutingKeys.ADMIN_INVITE_SENT,
            RoutingKeys.PASSWORD_RESET_REQUESTED,
        ],
    )
    _publisher = EventPublisher(_broker, settings.SERVICE_NAME)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if not _session_factory:
        raise RuntimeError("Database not initialized")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_broker() -> RabbitMQBroker | None:
    return _broker


def get_publisher() -> EventPublisher:
    if not _publisher:
        raise RuntimeError("Event publisher not initialized")
    return _publisher
