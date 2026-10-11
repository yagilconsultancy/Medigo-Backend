from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services import ride_access
from mediride_common.auth.models import UserClaims
from mediride_common.exceptions import NotFoundError
from mediride_common.schemas.enums import UserRole


def _ride(rider, driver=None, caregiver=None):
    return {
        "id": str(uuid4()),
        "rider_id": str(rider),
        "driver_id": str(driver) if driver else None,
        "caregiver_id": str(caregiver) if caregiver else None,
    }


def _patch_ride(monkeypatch, ride):
    client = SimpleNamespace(get_ride=AsyncMock(return_value=ride))
    monkeypatch.setattr(ride_access, "RideServiceClient", lambda url: client)
    return client


def _user(role):
    return UserClaims(id=uuid4(), role=role)


@pytest.mark.asyncio
async def test_rider_of_the_ride_is_allowed(monkeypatch):
    rider = _user(UserRole.RIDER)
    _patch_ride(monkeypatch, _ride(rider.id))
    await ride_access.ensure_can_view_ride(rider, uuid4())


@pytest.mark.asyncio
async def test_assigned_driver_is_allowed(monkeypatch):
    driver = _user(UserRole.DRIVER)
    _patch_ride(monkeypatch, _ride(uuid4(), driver=driver.id))
    await ride_access.ensure_can_view_ride(driver, uuid4())


@pytest.mark.asyncio
async def test_caregiver_is_allowed(monkeypatch):
    caregiver = _user(UserRole.RIDER)
    _patch_ride(monkeypatch, _ride(uuid4(), caregiver=caregiver.id))
    await ride_access.ensure_can_view_ride(caregiver, uuid4())


@pytest.mark.asyncio
async def test_admin_is_allowed_without_calling_ride_service(monkeypatch):
    client = _patch_ride(monkeypatch, None)
    await ride_access.ensure_can_view_ride(_user(UserRole.ADMIN), uuid4())
    client.get_ride.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [UserRole.RIDER, UserRole.DRIVER])
async def test_stranger_gets_not_found(monkeypatch, role):
    _patch_ride(monkeypatch, _ride(uuid4(), driver=uuid4()))
    with pytest.raises(NotFoundError):
        await ride_access.ensure_can_view_ride(_user(role), uuid4())


@pytest.mark.asyncio
async def test_unknown_ride_gets_not_found(monkeypatch):
    _patch_ride(monkeypatch, None)
    with pytest.raises(NotFoundError):
        await ride_access.ensure_can_view_ride(_user(UserRole.RIDER), uuid4())


def test_simulate_location_requires_admin():
    """The GPS simulator must never be callable without an admin token."""
    import inspect

    from app.api.v1 import test_location_endpoints as module

    params = inspect.signature(module.simulate_driver_location).parameters
    assert "_admin" in params
    dependency = params["_admin"].default.dependency
    assert dependency.__closure__ is not None  # built by require_role([...])
