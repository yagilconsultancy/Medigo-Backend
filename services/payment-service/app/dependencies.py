from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clients.stripe_client import StripeClient
from app.config import settings
from mediride_common.database.base import get_async_engine, get_async_session_factory
from mediride_common.events.broker import RabbitMQBroker
from mediride_common.events.publisher import EventPublisher

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_broker: RabbitMQBroker | None = None
_publisher: EventPublisher | None = None
_stripe_client: StripeClient | None = None


async def init_db() -> None:
    global _engine, _session_factory
    _engine = get_async_engine(settings.DATABASE_URL)
    _session_factory = get_async_session_factory(_engine)


async def init_broker() -> None:
    global _broker, _publisher
    _broker = RabbitMQBroker(settings.RABBITMQ_URL)
    await _broker.connect()
    _publisher = EventPublisher(_broker, settings.SERVICE_NAME)


def init_stripe() -> None:
    global _stripe_client
    _stripe_client = StripeClient(
        secret_key=settings.STRIPE_SECRET_KEY,
        publishable_key=settings.STRIPE_PUBLISHABLE_KEY,
        webhook_secret=settings.STRIPE_WEBHOOK_SECRET,
        environment=settings.ENVIRONMENT,
        mock_in_development=settings.STRIPE_MOCK_IN_DEVELOPMENT,
    )


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


def get_stripe_client() -> StripeClient:
    if not _stripe_client:
        raise RuntimeError("Stripe client not initialized")
    return _stripe_client
