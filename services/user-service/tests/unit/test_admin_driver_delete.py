from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.admin_driver_service import AdminDriverService


@pytest.mark.asyncio
async def test_delete_driver_removes_user_data_and_auth_credential():
    repo = MagicMock()
    repo.get_driver_detail = AsyncMock(return_value={"user_id": uuid4()})
    repo.delete_driver_account = AsyncMock()

    publisher = MagicMock()
    publisher.publish = AsyncMock()

    auth_client = MagicMock()
    auth_client.delete_account = AsyncMock(return_value=True)

    service = AdminDriverService(
        repo=repo,
        publisher=publisher,
        auth_client=auth_client,
        ride_client=MagicMock(),
    )

    driver_id = uuid4()
    admin_id = uuid4()

    result = await service.delete_driver(driver_id, admin_id)

    assert result["deleted"] is True
    assert result["driver_id"] == str(driver_id)
    repo.delete_driver_account.assert_awaited_once_with(driver_id)
    auth_client.delete_account.assert_awaited_once_with(driver_id)
    publisher.publish.assert_awaited_once()
