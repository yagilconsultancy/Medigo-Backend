import sys
import types
from datetime import date, datetime, timezone
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

from app.services.ride_service import RideService
from app.models.ride import Ride
from mediride_common.exceptions import ValidationError
from mediride_common.schemas.enums import (
    RecurringFrequency,
    RideStatus,
    RideType,
    TripStructure,
    TripType,
    UserRole,
)


class _FakeRideRepo:
    def __init__(self):
        self.created = []
        self.by_id = {}

    async def create(self, ride):
        if ride.id is None:
            ride.id = uuid4()
        self.created.append(ride)
        self.by_id[ride.id] = ride
        return ride

    async def get_by_id(self, ride_id):
        return self.by_id.get(ride_id)

    async def update(self, ride_id, **kwargs):
        ride = self.by_id[ride_id]
        for key, value in kwargs.items():
            setattr(ride, key, value)
        return ride


class _FakeStatusLogRepo:
    def __init__(self):
        self.created = []

    async def create(self, log):
        self.created.append(log)
        return log


class _FakeRecurringRideRepo:
    def __init__(self):
        self.created = []

    async def create(self, recurring_ride):
        if recurring_ride.id is None:
            recurring_ride.id = uuid4()
        self.created.append(recurring_ride)
        return recurring_ride


class _FakePublisher:
    def __init__(self):
        self.events = []

    async def publish(self, exchange, routing_key, payload):
        self.events.append((exchange, routing_key, payload))


class _FakePaymentClient:
    async def estimate_ride(self, **kwargs):
        return {
            "distance_miles": 10.0,
            "duration_minutes": 20,
            "total_fare": 25.5,
        }


class _FakeUserClient:
    pass


def _build_service():
    return RideService(
        ride_repo=_FakeRideRepo(),
        request_repo=None,
        status_log_repo=_FakeStatusLogRepo(),
        rating_repo=None,
        recurring_ride_repo=_FakeRecurringRideRepo(),
        publisher=_FakePublisher(),
        user_client=_FakeUserClient(),
        payment_client=_FakePaymentClient(),
    )


@pytest.mark.asyncio
async def test_create_ride_with_daily_recurrence_creates_future_requested_rides():
    service = _build_service()
    rider_id = uuid4()

    ride = await service.create_ride(
        rider_id=rider_id,
        ride_type=RideType.AMBULATORY,
        trip_type=TripType.TRANSPORT_ONLY,
        trip_structure=TripStructure.ONE_WAY,
        pickup_address="Toronto Pearson International Airport",
        destination_address="Toronto Premium Outlets",
        scheduled_at=datetime(2026, 5, 12, 11, 0, tzinfo=timezone.utc),
        recurring_frequency=RecurringFrequency.DAILY,
        recurring_end_date=date(2026, 5, 14),
    )

    assert len(service.ride_repo.created) == 3
    assert len(service.status_log_repo.created) == 3
    assert len(service.recurring_ride_repo.created) == 1
    assert ride.id == service.ride_repo.created[0].id

    recurring_ride_id = service.recurring_ride_repo.created[0].id
    assert all(created.recurring_ride_id == recurring_ride_id for created in service.ride_repo.created)
    assert all(log.to_status == RideStatus.REQUESTED for log in service.status_log_repo.created)
    assert service.status_log_repo.created[1].notes == f"Generated from recurring series {recurring_ride_id}"


@pytest.mark.asyncio
async def test_create_ride_with_recurrence_requires_end_date():
    service = _build_service()

    with pytest.raises(ValidationError, match="recurring_end_date is required"):
        await service.create_ride(
            rider_id=uuid4(),
            ride_type=RideType.AMBULATORY,
            trip_type=TripType.TRANSPORT_ONLY,
            trip_structure=TripStructure.ONE_WAY,
            pickup_address="A",
            destination_address="B",
            scheduled_at=datetime(2026, 5, 12, 11, 0, tzinfo=timezone.utc),
            recurring_frequency=RecurringFrequency.DAILY,
        )


@pytest.mark.asyncio
async def test_rebook_ride_preserves_passenger_contact_fields():
    service = _build_service()
    rider_id = uuid4()
    original = Ride(
        id=uuid4(),
        rider_id=rider_id,
        ride_type=RideType.AMBULATORY,
        trip_type=TripType.TRANSPORT_ONLY,
        trip_structure=TripStructure.ONE_WAY,
        pickup_address="A",
        destination_address="B",
        scheduled_at=datetime(2026, 5, 12, 11, 0, tzinfo=timezone.utc),
        status=RideStatus.COMPLETED,
        passenger_first_name="Ada",
        passenger_last_name="Lovelace",
        passenger_phone="+14165550123",
    )
    service.ride_repo.by_id[original.id] = original

    rebooked = await service.rebook_ride(
        original.id,
        rider_id,
        datetime(2026, 5, 14, 11, 0, tzinfo=timezone.utc),
    )

    assert rebooked.passenger_first_name == "Ada"
    assert rebooked.passenger_last_name == "Lovelace"
    assert rebooked.passenger_phone == "+14165550123"


@pytest.mark.asyncio
async def test_driver_cancel_unassigns_themselves_instead_of_cancelling_the_ride():
    service = _build_service()
    rider_id = uuid4()
    driver_id = uuid4()
    ride = Ride(
        id=uuid4(),
        rider_id=rider_id,
        driver_id=driver_id,
        ride_type=RideType.AMBULATORY,
        trip_type=TripType.TRANSPORT_ONLY,
        trip_structure=TripStructure.ONE_WAY,
        pickup_address="A",
        destination_address="B",
        scheduled_at=datetime(2026, 5, 12, 11, 0, tzinfo=timezone.utc),
        status=RideStatus.DRIVER_ASSIGNED,
    )
    service.ride_repo.by_id[ride.id] = ride

    result = await service.cancel_ride(
        ride.id,
        driver_id,
        "I need to step away",
        actor_role=UserRole.DRIVER,
    )

    assert result.status == RideStatus.CONFIRMED
    assert result.driver_id is None
    assert result.cancelled_by is None
    assert result.cancellation_reason is None
    assert service.status_log_repo.created[-1].to_status == RideStatus.CONFIRMED
