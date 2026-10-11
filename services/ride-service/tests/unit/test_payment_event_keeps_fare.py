"""A payment event may fill in a missing fare but never overwrite a stored one."""
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.events import consumers
from mediride_common.events.constants import RoutingKeys
from mediride_common.schemas.enums import RideStatus


class _Repo:
    def __init__(self, ride):
        self.ride = ride
        self.updates = []

    async def get_by_id(self, ride_id):
        return self.ride

    async def update(self, ride_id, **kwargs):
        self.updates.append(kwargs)


class _Logs:
    async def create(self, log):
        pass


def _run(monkeypatch, ride):
    repo = _Repo(ride)

    async def fake_get_db():
        yield object()

    monkeypatch.setattr(consumers, "get_db", fake_get_db)
    monkeypatch.setattr(consumers, "RideRepository", lambda session: repo)
    monkeypatch.setattr(consumers, "StatusLogRepository", lambda session: _Logs())
    ride_id = uuid4()
    envelope = SimpleNamespace(
        event_type=RoutingKeys.PAYMENT_COMPLETED,
        payload={
            "transaction_id": str(uuid4()), "ride_id": str(ride_id), "user_id": str(uuid4()),
            "amount": 1.0, "status": "completed",
        },
    )
    consumer = consumers.PaymentEventConsumer.__new__(consumers.PaymentEventConsumer)
    return repo, consumer, envelope


@pytest.mark.asyncio
async def test_existing_final_fare_is_not_overwritten(monkeypatch):
    repo, consumer, envelope = _run(
        monkeypatch, SimpleNamespace(final_fare=52.5, status=RideStatus.COMPLETED)
    )
    await consumer.handle(envelope)
    assert all("final_fare" not in u for u in repo.updates)


@pytest.mark.asyncio
async def test_missing_final_fare_is_filled_and_ride_moves_to_requested(monkeypatch):
    repo, consumer, envelope = _run(
        monkeypatch, SimpleNamespace(final_fare=None, status=RideStatus.PENDING)
    )
    await consumer.handle(envelope)
    assert {"final_fare": 1.0} in repo.updates
    assert {"status": RideStatus.REQUESTED} in repo.updates
