from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.repositories.push_token_repo import PushTokenRepository


@pytest.mark.asyncio
async def test_registering_a_token_removes_it_from_other_users():
    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()

    await PushTokenRepository(session).upsert(uuid4(), "device-token-1", "ios")

    first_statement = str(session.execute.await_args_list[0].args[0]).upper()
    assert first_statement.startswith("DELETE")
    assert "TOKEN" in first_statement and "USER_ID" in first_statement
