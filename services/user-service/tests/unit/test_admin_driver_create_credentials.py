"""create_driver must never hand out (or email) a known password."""
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.admin_driver import CreateDriverRequest
from app.services.admin_driver_service import AdminDriverService
from mediride_common.events.constants import RoutingKeys


def _build():
    user_id = uuid4()
    repo = MagicMock()
    repo.create_user = AsyncMock()
    repo.create_driver_profile = AsyncMock()
    repo.session = MagicMock()
    repo.session.commit = AsyncMock()
    repo.get_driver_detail = AsyncMock(return_value=None)

    publisher = MagicMock()
    publisher.publish = AsyncMock()

    auth_client = MagicMock()
    auth_client.send_driver_activation_code = AsyncMock(return_value=True)
    auth_client.create_driver_credential = AsyncMock(
        return_value={"user_id": str(user_id), "email": "d@example.com"}
    )

    service = AdminDriverService(
        repo=repo, publisher=publisher, auth_client=auth_client, ride_client=MagicMock()
    )
    service.get_driver_detail = AsyncMock(return_value=MagicMock())
    return service, auth_client, publisher


@pytest.mark.asyncio
async def test_create_driver_uses_random_unverified_credential_and_sends_no_password():
    request = CreateDriverRequest(
        first_name="A", last_name="B", email="d@example.com", fleet_id=uuid4(), is_approved=True
    )

    service_a, auth_a, pub_a = _build()
    await service_a.create_driver(uuid4(), request)
    service_b, auth_b, _ = _build()
    await service_b.create_driver(uuid4(), request)

    kwargs_a = auth_a.create_driver_credential.await_args.kwargs
    kwargs_b = auth_b.create_driver_credential.await_args.kwargs

    assert kwargs_a["is_verified"] is False
    assert kwargs_a["password"] != "MediRide2026!"
    assert kwargs_a["password"] != kwargs_b["password"]  # random per driver
    assert len(kwargs_a["password"]) >= 24

    routing_keys = [c.args[1] for c in pub_a.publish.await_args_list]
    assert RoutingKeys.DRIVER_INVITE_SENT not in routing_keys
    assert RoutingKeys.DRIVER_ACCOUNT_CREATED in routing_keys
    for c in pub_a.publish.await_args_list:
        assert "password" not in str(c.args[2]).lower()


@pytest.mark.asyncio
async def test_approved_driver_gets_activation_code_and_active_status():
    service, auth, _ = _build()
    request = CreateDriverRequest(
        first_name="A", last_name="B", email="d@example.com", fleet_id=uuid4(), is_approved=True
    )
    await service.create_driver(uuid4(), request)
    auth.send_driver_activation_code.assert_awaited_once()
    profile = service.repo.create_driver_profile.await_args.kwargs
    assert profile["is_approved"] is True
    assert profile["account_status"] == "active"


@pytest.mark.asyncio
async def test_unapproved_driver_gets_no_code_yet():
    service, auth, _ = _build()
    request = CreateDriverRequest(
        first_name="A", last_name="B", email="d@example.com", fleet_id=uuid4(), is_approved=False
    )
    await service.create_driver(uuid4(), request)
    auth.send_driver_activation_code.assert_not_awaited()


@pytest.mark.asyncio
async def test_approve_driver_sends_code_after_commit():
    service, auth, _ = _build()
    driver_id = uuid4()
    service.repo.get_driver_detail = AsyncMock(return_value={"user_id": driver_id})
    service.repo.update_driver_profile = AsyncMock()
    service.repo.create_suspension_log = AsyncMock()
    await service.approve_driver(driver_id, uuid4())
    service.repo.session.commit.assert_awaited()
    auth.send_driver_activation_code.assert_awaited_once_with(driver_id)


@pytest.mark.asyncio
async def test_admin_created_driver_is_marked_onboarded():
    """Otherwise the app sends the driver into the old registration flow after login."""
    service, _, _ = _build()
    request = CreateDriverRequest(
        first_name="A", last_name="B", email="d@example.com", fleet_id=uuid4(), is_approved=True
    )
    await service.create_driver(uuid4(), request)
    user = service.repo.create_user.await_args.kwargs
    assert user["onboarding_completed"] is True
    assert user["onboarding_step"] == 5
