from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from mediride_common.database.base import get_async_engine, get_async_session_factory

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    global _engine, _session_factory
    _engine = get_async_engine(settings.DATABASE_URL)
    _session_factory = get_async_session_factory(_engine)


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


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if not _session_factory:
        raise RuntimeError("Database not initialized")
    return _session_factory
