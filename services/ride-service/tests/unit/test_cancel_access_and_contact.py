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

from app.api.v1.ride_endpoints import cancel_ride
from app.schemas.ride import CancelRideRequest, DriverContactResponse
from mediride_common.auth.models import UserClaims
from mediride_common.exceptions import NotFoundError
from mediride_common.schemas.enums import UserRole


def _user(role, user_id=None):
    return UserClaims(id=user_id or uuid4(), role=role)


class _FakeService:
    def __init__(self, ride):
        self.ride = ride
        self.cancelled = []

    async def get_ride(self, ride_id):
        return self.ride

    async def cancel_ride(self, ride_id, cancelled_by, reason, actor_role=None):
        self.cancelled.append((cancelled_by, reason))
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
            status="cancelled",
            created_at=datetime.now(timezone.utc),
        )


def _ride(rider_id=None, driver_id=None):
    return SimpleNamespace(
        id=uuid4(),
        rider_id=rider_id or uuid4(),
        driver_id=driver_id,
        caregiver_id=None,
    )


@pytest.mark.asyncio
async def test_rider_cannot_cancel_someone_elses_ride():
    ride = _ride()
    service = _FakeService(ride)
    with pytest.raises(NotFoundError):
        await cancel_ride(
            ride.id,
            CancelRideRequest(reason="not mine"),
            user=_user(UserRole.RIDER),
            service=service,
        )
    assert service.cancelled == []


@pytest.mark.asyncio
async def test_unassigned_driver_cannot_cancel_a_ride():
    ride = _ride(driver_id=uuid4())
    service = _FakeService(ride)
    with pytest.raises(NotFoundError):
        await cancel_ride(
            ride.id,
            CancelRideRequest(reason="not mine"),
            user=_user(UserRole.DRIVER),
            service=service,
        )
    assert service.cancelled == []


@pytest.mark.asyncio
async def test_owner_can_cancel_their_own_ride():
    owner = uuid4()
    ride = _ride(rider_id=owner)
    service = _FakeService(ride)
    result = await cancel_ride(
        ride.id,
        CancelRideRequest(reason="change of plans"),
        user=_user(UserRole.RIDER, owner),
        service=service,
    )
    assert service.cancelled == [(owner, "change of plans")]
    assert result.data.status == "cancelled"


@pytest.mark.asyncio
async def test_admin_can_cancel_any_ride():
    ride = _ride()
    service = _FakeService(ride)
    admin = uuid4()
    await cancel_ride(
        ride.id,
        CancelRideRequest(reason="ops"),
        user=_user(UserRole.ADMIN, admin),
        service=service,
    )
    assert service.cancelled == [(admin, "ops")]


def test_driver_contact_allows_a_driver_with_no_ratings():
    contact = DriverContactResponse(
        driver_id=str(uuid4()),
        first_name="New",
        last_name="Driver",
        rating=None,
    )
    assert contact.rating is None


def test_driver_contact_keeps_a_real_rating():
    contact = DriverContactResponse(
        driver_id=str(uuid4()),
        first_name="Old",
        last_name="Hand",
        rating=4.5,
    )
    assert contact.rating == 4.5
