import sys
import types
from datetime import datetime, timezone
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

from app.models.admin_note import AdminNote
from app.models.ride import Ride
from app.services.admin_booking_service import AdminBookingService
from app.services.ride_service import RideService
from mediride_common.events.constants import RoutingKeys
from mediride_common.schemas.enums import RideStatus


class _FakeRideRepo:
    def __init__(self, ride):
        self.ride = ride

    async def get_by_id(self, ride_id):
        return self.ride


class _FakeNoteRepo:
    """Stores notes and honours the driver-visibility filter like the real repo."""

    def __init__(self, notes=None):
        self.notes = list(notes or [])

    async def create(self, note):
        if note.is_driver_visible is None:
            note.is_driver_visible = False
        note.id = note.id or uuid4()
        note.created_at = note.created_at or datetime.now(timezone.utc)
        self.notes.append(note)
        return note

    async def get_by_ride(self, ride_id):
        return [n for n in self.notes if n.ride_id == ride_id]

    async def get_driver_visible_by_ride(self, ride_id):
        return [
            n
            for n in self.notes
            if n.ride_id == ride_id and n.is_driver_visible
        ]


class _FakePublisher:
    def __init__(self):
        self.published = []

    async def publish(self, exchange, routing_key, payload, correlation_id=""):
        self.published.append((routing_key, payload))


class _FakeStatusLogRepo:
    async def get_by_ride(self, ride_id):
        return []


class _FakeRatingRepo:
    async def get_by_ride_and_type(self, ride_id, rating_type):
        return None


class _FakeUserClient:
    async def get_user_profile(self, user_id):
        return {"first_name": "Ada", "last_name": "Lovelace"}


def _make_note(ride_id, content, *, is_driver_visible):
    return AdminNote(
        id=uuid4(),
        ride_id=ride_id,
        author_id=uuid4(),
        author_type="admin",
        content=content,
        is_driver_visible=is_driver_visible,
        created_at=datetime.now(timezone.utc),
    )


def _make_ride(driver_id=None):
    return Ride(
        id=uuid4(),
        rider_id=uuid4(),
        driver_id=driver_id,
        status=RideStatus.DRIVER_ASSIGNED,
        pickup_address="1 Main St",
        destination_address="2 Oak Ave",
        scheduled_at=datetime.now(timezone.utc),
    )


def _make_admin_service(ride, note_repo, publisher):
    service = AdminBookingService.__new__(AdminBookingService)
    service.ride_repo = _FakeRideRepo(ride)
    service.note_repo = note_repo
    service.publisher = publisher
    return service


@pytest.mark.asyncio
async def test_ride_detail_exposes_only_driver_visible_notes():
    """Internal admin notes must never reach a driver-facing ride detail."""
    ride = _make_ride(driver_id=uuid4())
    note_repo = _FakeNoteRepo(
        [
            _make_note(ride.id, "Rider owes a balance", is_driver_visible=False),
            _make_note(ride.id, "Use the rear entrance", is_driver_visible=True),
        ]
    )

    service = RideService.__new__(RideService)
    service.ride_repo = _FakeRideRepo(ride)
    service.status_log_repo = _FakeStatusLogRepo()
    service.rating_repo = _FakeRatingRepo()
    service.user_client = _FakeUserClient()
    service.admin_note_repo = note_repo

    detail = await service.get_ride_detail(ride.id)

    contents = [n.content for n in detail["driver_notes"]]
    assert contents == ["Use the rear entrance"]
    assert "Rider owes a balance" not in contents


@pytest.mark.asyncio
async def test_ride_detail_reports_no_notes_when_repo_absent():
    """The note repo is optional, so detail must not blow up without it."""
    ride = _make_ride()

    service = RideService.__new__(RideService)
    service.ride_repo = _FakeRideRepo(ride)
    service.status_log_repo = _FakeStatusLogRepo()
    service.rating_repo = _FakeRatingRepo()
    service.user_client = _FakeUserClient()
    service.admin_note_repo = None

    detail = await service.get_ride_detail(ride.id)

    assert detail["driver_notes"] == []


@pytest.mark.asyncio
async def test_driver_visible_note_notifies_the_assigned_driver():
    driver_id = uuid4()
    ride = _make_ride(driver_id=driver_id)
    publisher = _FakePublisher()
    service = _make_admin_service(ride, _FakeNoteRepo(), publisher)

    await service.add_note(
        ride.id, uuid4(), "Call on arrival", is_driver_visible=True
    )

    routing_keys = [rk for rk, _ in publisher.published]
    assert RoutingKeys.RIDE_NOTE_ADDED in routing_keys
    payload = dict(publisher.published[0][1])
    assert payload["driver_id"] == str(driver_id)
    assert payload["ride_id"] == str(ride.id)


@pytest.mark.asyncio
async def test_internal_note_does_not_notify_the_driver():
    ride = _make_ride(driver_id=uuid4())
    publisher = _FakePublisher()
    service = _make_admin_service(ride, _FakeNoteRepo(), publisher)

    await service.add_note(
        ride.id, uuid4(), "Internal: flagged for billing", is_driver_visible=False
    )

    assert publisher.published == []


@pytest.mark.asyncio
async def test_driver_visible_note_on_unassigned_ride_publishes_nothing():
    """No driver yet means nobody to notify — and no crash on a None driver_id."""
    ride = _make_ride(driver_id=None)
    publisher = _FakePublisher()
    service = _make_admin_service(ride, _FakeNoteRepo(), publisher)

    note = await service.add_note(
        ride.id, uuid4(), "Use the rear entrance", is_driver_visible=True
    )

    assert note.is_driver_visible is True
    assert publisher.published == []
