from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def get_async_engine(database_url: str, **kwargs) -> AsyncEngine:
    return create_async_engine(
        database_url,
        echo=kwargs.pop("echo", False),
        pool_size=kwargs.pop("pool_size", 10),
        max_overflow=kwargs.pop("max_overflow", 20),
        pool_pre_ping=True,
        **kwargs,
    )


def get_async_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
