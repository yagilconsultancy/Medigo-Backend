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

from app.api.v1.ride_endpoints import _RIDE_DETAIL_EXPLICIT_FIELDS, get_ride_detail
from app.schemas.ride import RideDetailResponse, RideResponse
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole


def _fake_ride():
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        rider_id=uuid4(),
        driver_id=uuid4(),
        caregiver_id=None,
        business_id=None,
        ride_type="standard",
        trip_type="one_way",
        trip_structure="single",
        pickup_address="1 Main St",
        pickup_latitude=43.0,
        pickup_longitude=-81.0,
        destination_address="2 Side St",
        destination_latitude=43.1,
        destination_longitude=-81.1,
        scheduled_at=now,
        pickup_at=None,
        dropoff_at=None,
        status="assigned",
        estimated_distance_miles=3.2,
        actual_distance_miles=None,
        estimated_duration_minutes=12,
        actual_duration_minutes=None,
        mobility_level="ambulatory",
        assistance_level="door_to_door",
        appointment_time=None,
        cancellation_reason=None,
        cancelled_at=None,
        created_at=now,
    )


class _FakeService:
    def __init__(self, ride):
        self.ride = ride

    async def get_ride(self, ride_id):
        return self.ride

    async def get_ride_detail(self, ride_id):
        return {
            "ride": self.ride,
            "rider_name": "Test Rider",
            "rider_rating": 5.0,
            "rider_trip_count": 3,
            "driver_rating": None,
            "rider_rating_given": None,
            "timeline": [],
            "driver_notes": [],
        }


@pytest.mark.asyncio
async def test_ride_detail_returns_levels_without_duplicate_keyword_error():
    ride = _fake_ride()
    admin = UserClaims(id=uuid4(), role=UserRole.ADMIN)
    result = await get_ride_detail(ride.id, user=admin, service=_FakeService(ride))
    assert result.data.mobility_level == "ambulatory"
    assert result.data.assistance_level == "door_to_door"
    assert result.data.rider_name == "Test Rider"


def test_explicit_fields_exist_on_detail_response():
    assert _RIDE_DETAIL_EXPLICIT_FIELDS <= set(RideDetailResponse.model_fields)
    shared = set(RideResponse.model_fields) & _RIDE_DETAIL_EXPLICIT_FIELDS
    assert {"mobility_level", "assistance_level"} <= shared
