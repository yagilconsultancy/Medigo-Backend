import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_publisher
from app.main import app
from mediride_common.events.publisher import EventPublisher


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
async def client(mock_publisher):
    app.dependency_overrides[get_publisher] = lambda: mock_publisher

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
