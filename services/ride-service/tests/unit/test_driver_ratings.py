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
for _n in (
    "AbstractChannel",
    "AbstractConnection",
    "AbstractExchange",
    "AbstractIncomingMessage",
):
    setattr(aio_pika_abc_stub, _n, object)
sys.modules.setdefault("aio_pika", aio_pika_stub)
sys.modules.setdefault("aio_pika.abc", aio_pika_abc_stub)

from app.api.v1.driver_ride_endpoints import get_driver_stats, get_my_ratings
from app.schemas.rating import DriverRatingsResponse
from app.schemas.ride import DriverStatsResponse
from app.services.ride_service import RideService
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole


class FakeRatingRepo:
    def __init__(self, avg, count, rows=()):
        self._summary = (avg, count)
        self._rows = list(rows)

    async def get_rating_summary(self, user_id):
        return self._summary

    async def get_ratings_for_user(self, user_id, offset=0, limit=20):
        return self._rows, len(self._rows)


class FakeRideRepo:
    async def get_driver_stats(self, driver_id):
        return {
            "total_trips": 3,
            "hours_online": 1.5,
            "average_earnings": 10.0,
        }

    async def get_driver_earnings_today(self, driver_id, start):
        return 0.0


def _service(rating_repo):
    return RideService(
        ride_repo=FakeRideRepo(),
        request_repo=None,
        status_log_repo=None,
        rating_repo=rating_repo,
        recurring_ride_repo=None,
        publisher=None,
        user_client=None,
    )


def _driver():
    return UserClaims(id=uuid4(), role=UserRole.DRIVER)


@pytest.mark.asyncio
async def test_stats_have_no_rating_when_driver_unrated():
    stats = await _service(FakeRatingRepo(None, 0)).get_driver_stats(uuid4())
    assert stats["rating"] is None
    assert stats["total_ratings"] == 0
    # Must still serialise through the response model.
    assert DriverStatsResponse(**stats).rating is None


@pytest.mark.asyncio
async def test_stats_use_real_average():
    stats = await _service(FakeRatingRepo(4.5, 2)).get_driver_stats(uuid4())
    assert stats["rating"] == 4.5
    assert stats["total_ratings"] == 2


@pytest.mark.asyncio
async def test_my_ratings_empty_has_no_average():
    resp = await get_my_ratings(
        page=1, limit=20, user=_driver(), service=_service(FakeRatingRepo(None, 0))
    )
    assert resp.data.average_rating is None
    assert resp.data.total_ratings == 0
    assert resp.data.ratings == []


@pytest.mark.asyncio
async def test_my_ratings_hides_rider_identity():
    row = SimpleNamespace(
        id=uuid4(),
        ride_id=uuid4(),
        rated_user_id=uuid4(),
        rated_by_user_id=uuid4(),
        rating_type="rider_to_driver",
        rating=5,
        comment="Great driver",
        created_at=datetime.now(timezone.utc),
    )
    resp = await get_my_ratings(
        page=1,
        limit=20,
        user=_driver(),
        service=_service(FakeRatingRepo(5.0, 1, [row])),
    )
    assert resp.data.average_rating == 5.0
    assert resp.data.ratings[0].comment == "Great driver"
    dumped = DriverRatingsResponse.model_dump(resp.data)
    assert set(dumped["ratings"][0]) == {"rating", "comment", "created_at"}
