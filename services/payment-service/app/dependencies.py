from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clients.moneris_client import MonerisClient
from app.config import settings
from mediride_common.database.base import get_async_engine, get_async_session_factory
from mediride_common.events.broker import RabbitMQBroker
from mediride_common.events.publisher import EventPublisher

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_broker: RabbitMQBroker | None = None
_publisher: EventPublisher | None = None
_moneris_client: MonerisClient | None = None


async def init_db() -> None:
    global _engine, _session_factory
    _engine = get_async_engine(settings.DATABASE_URL)
    _session_factory = get_async_session_factory(_engine)


async def init_broker() -> None:
    global _broker, _publisher
    _broker = RabbitMQBroker(settings.RABBITMQ_URL)
    await _broker.connect()
    _publisher = EventPublisher(_broker, settings.SERVICE_NAME)


def init_moneris() -> None:
    global _moneris_client
    _moneris_client = MonerisClient(
        client_id=settings.MONERIS_CLIENT_ID,
        client_secret=settings.MONERIS_CLIENT_SECRET,
        store_id=settings.MONERIS_STORE_ID,
        sandbox=settings.MONERIS_SANDBOX,
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


def get_moneris_client() -> MonerisClient:
    if not _moneris_client:
        raise RuntimeError("Moneris client not initialized")
    return _moneris_client
