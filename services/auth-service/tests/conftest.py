import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.dependencies import get_db, get_publisher
from app.main import app
from mediride_common.database.base import Base
from mediride_common.events.publisher import EventPublisher


# Use in-memory SQLite for tests (simplified)
# In real CI, use a test PostgreSQL instance
TEST_DATABASE_URL = settings.DATABASE_URL


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def mock_publisher():
    publisher = MagicMock(spec=EventPublisher)
    publisher.publish = AsyncMock()
    return publisher


@pytest_asyncio.fixture
async def client(mock_publisher) -> AsyncGenerator[AsyncClient, None]:
    # Override publisher dependency
    app.dependency_overrides[get_publisher] = lambda: mock_publisher

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
