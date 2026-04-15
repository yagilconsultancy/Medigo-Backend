from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from mediride_common.database.base import get_async_engine, get_async_session_factory
from mediride_common.events.broker import RabbitMQBroker
from mediride_common.events.publisher import EventPublisher
from mediride_common.storage.s3_client import S3StorageClient

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_broker: RabbitMQBroker | None = None
_publisher: EventPublisher | None = None
_s3_client: S3StorageClient | None = None


async def init_db() -> None:
    global _engine, _session_factory
    _engine = get_async_engine(settings.DATABASE_URL)
    _session_factory = get_async_session_factory(_engine)


async def init_broker() -> None:
    global _broker, _publisher
    _broker = RabbitMQBroker(settings.RABBITMQ_URL)
    await _broker.connect()
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


async def init_s3() -> None:
    global _s3_client
    _s3_client = S3StorageClient(
        endpoint_url=settings.S3_ENDPOINT_URL,
        access_key=settings.S3_ACCESS_KEY,
        secret_key=settings.S3_SECRET_KEY,
        region=settings.S3_REGION,
    )
    await _s3_client.ensure_bucket_exists(settings.S3_BUCKET_DOCUMENTS)


def get_s3_client() -> S3StorageClient:
    if not _s3_client:
        raise RuntimeError("S3 client not initialized")
    return _s3_client


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the session factory for creating new sessions (used by consumers)."""
    if not _session_factory:
        raise RuntimeError("Database not initialized")
    return _session_factory
