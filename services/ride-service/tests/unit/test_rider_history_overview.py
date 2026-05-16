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

from app.services.ride_service import RideService


class _FakeRideRepo:
    def __init__(self, rides, filtered_total, summary):
        self.rides = rides
        self.filtered_total = filtered_total
        self.summary = summary

    async def get_by_rider(self, rider_id, status_filter, offset, limit):
        return self.rides, self.filtered_total

    async def get_rider_history_summary(self, rider_id):
        return self.summary


class _FakeRatingRepo:
    async def get_average_rating_given(self, user_id, rating_type):
        return 4.92


class _FakeUserClient:
    async def get_user_profile(self, user_id):
        return {"created_at": "2024-01-15T09:30:00+00:00"}


@pytest.mark.asyncio
async def test_get_rider_history_overview_builds_summary_stats_and_pagination():
    rides = [types.SimpleNamespace(id=uuid4()), types.SimpleNamespace(id=uuid4())]
    service = RideService(
        ride_repo=_FakeRideRepo(
            rides=rides,
            filtered_total=6,
            summary={
                "total_rides": 6,
                "completed_rides": 5,
                "cancelled_rides": 1,
                "miles_traveled": 41.1,
            },
        ),
        request_repo=None,
        status_log_repo=None,
        rating_repo=_FakeRatingRepo(),
        recurring_ride_repo=None,
        publisher=None,
        user_client=_FakeUserClient(),
        payment_client=None,
    )

    result = await service.get_rider_history_overview(
        rider_id=uuid4(),
        status_filter="completed",
        offset=0,
        limit=20,
    )

    assert result["summary"] == {
        "total_rides": 6,
        "completed_rides": 5,
        "cancelled_rides": 1,
        "miles_traveled": 41.1,
    }
    assert result["stats"] == {
        "total_rides": 6,
        "miles_traveled": 41.1,
        "average_rating_given": 4.9,
        "member_since": "Jan 2024",
    }
    assert result["rides"] == rides
    assert result["filtered_total"] == 6
    assert result["page"] == 1
    assert result["limit"] == 20
    assert result["total_pages"] == 1
    assert result["status_filter"] == "completed"

