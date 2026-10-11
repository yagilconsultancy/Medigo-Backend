import sys
import types
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

aio_pika_stub = types.ModuleType("aio_pika")
aio_pika_stub.ExchangeType = types.SimpleNamespace(TOPIC="topic", FANOUT="fanout")
aio_pika_stub.Message = object
aio_pika_stub.DeliveryMode = types.SimpleNamespace(PERSISTENT=2)
aio_pika_abc_stub = types.ModuleType("aio_pika.abc")
aio_pika_abc_stub.AbstractChannel = object
aio_pika_abc_stub.AbstractConnection = object
aio_pika_abc_stub.AbstractExchange = object
aio_pika_abc_stub.AbstractIncomingMessage = object
sys.modules.setdefault("aio_pika", aio_pika_stub)
sys.modules.setdefault("aio_pika.abc", aio_pika_abc_stub)

from app.api.v1.ride_endpoints import get_ride_timeline, transition_ride_status
from app.schemas.ride import StatusTransitionRequest
from app.services.ride_access import can_access_ride, ensure_ride_access
from mediride_common.auth.models import UserClaims
from mediride_common.exceptions import NotFoundError
from mediride_common.schemas.enums import UserRole


def _ride(rider_id=None, driver_id=None, caregiver_id=None):
    return SimpleNamespace(
        id=uuid4(),
        rider_id=rider_id or uuid4(),
        driver_id=driver_id,
        caregiver_id=caregiver_id,
    )


def _user(role, user_id=None):
    return UserClaims(id=user_id or uuid4(), role=role)


def test_admin_can_access_any_ride():
    assert can_access_ride(_ride(), _user(UserRole.ADMIN))


def test_assigned_driver_can_access_but_other_driver_cannot():
    driver = uuid4()
    ride = _ride(driver_id=driver)
    assert can_access_ride(ride, _user(UserRole.DRIVER, driver))
    assert not can_access_ride(ride, _user(UserRole.DRIVER))


def test_driver_cannot_access_ride_with_no_driver_assigned():
    assert not can_access_ride(_ride(driver_id=None), _user(UserRole.DRIVER))


def test_rider_and_facility_only_see_their_own_rides():
    owner = uuid4()
    ride = _ride(rider_id=owner)
    assert can_access_ride(ride, _user(UserRole.RIDER, owner))
    assert can_access_ride(ride, _user(UserRole.FACILITY, owner))
    assert not can_access_ride(ride, _user(UserRole.RIDER))
    assert not can_access_ride(ride, _user(UserRole.FACILITY))


def test_attached_caregiver_can_access():
    caregiver = uuid4()
    ride = _ride(caregiver_id=caregiver)
    assert can_access_ride(ride, _user(UserRole.RIDER, caregiver))


def test_business_role_has_no_access_through_these_endpoints():
    assert not can_access_ride(_ride(), _user(UserRole.BUSINESS))


def test_ensure_ride_access_raises_not_found_for_outsiders():
    with pytest.raises(NotFoundError):
        ensure_ride_access(_ride(), _user(UserRole.RIDER))


class _FakeService:
    def __init__(self, ride):
        self.ride = ride
        self.transitions = []
        self.timeline_calls = 0

    async def get_ride(self, ride_id):
        return self.ride

    async def get_ride_timeline(self, ride_id):
        self.timeline_calls += 1
        return []

    async def transition_status(self, ride_id, status, changed_by, notes):
        self.transitions.append((status, changed_by))
        return SimpleNamespace(
            id=ride_id,
            rider_id=self.ride.rider_id,
            driver_id=self.ride.driver_id,
            caregiver_id=None,
            business_id=None,
            ride_type="standard",
            trip_type="one_way",
            trip_structure="single",
            pickup_address="a",
            destination_address="b",
            scheduled_at=datetime.now(timezone.utc),
            status=status,
            created_at=datetime.now(timezone.utc),
        )


@pytest.mark.asyncio
async def test_other_driver_cannot_move_a_ride_through_its_statuses():
    ride = _ride(driver_id=uuid4())
    service = _FakeService(ride)
    intruder = _user(UserRole.DRIVER)
    with pytest.raises(NotFoundError):
        await transition_ride_status(
            ride.id,
            StatusTransitionRequest(status="completed"),
            user=intruder,
            service=service,
        )
    assert service.transitions == []


@pytest.mark.asyncio
async def test_assigned_driver_can_move_their_ride():
    driver = uuid4()
    ride = _ride(driver_id=driver)
    service = _FakeService(ride)
    result = await transition_ride_status(
        ride.id,
        StatusTransitionRequest(status="driver_en_route"),
        user=_user(UserRole.DRIVER, driver),
        service=service,
    )
    assert service.transitions == [("driver_en_route", driver)]
    assert result.data.status == "driver_en_route"


@pytest.mark.asyncio
async def test_timeline_hidden_from_other_riders():
    ride = _ride()
    service = _FakeService(ride)
    with pytest.raises(NotFoundError):
        await get_ride_timeline(ride.id, user=_user(UserRole.RIDER), service=service)
    assert service.timeline_calls == 0
