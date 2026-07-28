"""
Trip-count and on-trip bookkeeping driven by ride events.

Regression cover for the bug where driver_profiles.total_trips only ever moved
on ride.rating.submitted, so drivers whose completed trips went unrated were
shown 0 trips across the admin roster.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.events.consumers import RideLifecycleConsumer, RideRatingConsumer
from mediride_common.events.constants import RoutingKeys
from mediride_common.schemas.enums import RatingType


@asynccontextmanager
async def _patched_repo(repo):
    """Point both consumers at a stub session and stub DriverRepository."""

    async def fake_get_db():
        yield MagicMock()

    with patch("app.events.consumers.get_db", fake_get_db), patch(
        "app.events.consumers.DriverRepository", return_value=repo
    ):
        yield


def _driver_repo(**profile_attrs):
    repo = MagicMock()
    repo.set_trip_status = AsyncMock()
    repo.increment_total_trips = AsyncMock()
    repo.record_rating = AsyncMock()
    repo.update = AsyncMock()
    profile = MagicMock(**{"total_trips": 0, "total_ratings": 0, **profile_attrs})
    repo.get_by_user_id = AsyncMock(return_value=profile)
    return repo


def _envelope(event_type, payload):
    envelope = MagicMock()
    envelope.event_type = event_type
    envelope.payload = payload
    return envelope


@pytest.mark.asyncio
async def test_completed_ride_increments_total_trips():
    driver_id = uuid4()
    repo = _driver_repo()

    async with _patched_repo(repo):
        await RideLifecycleConsumer(MagicMock()).handle(
            _envelope(
                RoutingKeys.RIDE_COMPLETED,
                {"driver_id": str(driver_id), "ride_id": str(uuid4())},
            )
        )

    repo.increment_total_trips.assert_awaited_once_with(driver_id)
    repo.set_trip_status.assert_awaited_once_with(driver_id, is_on_trip=False)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event_type", [RoutingKeys.RIDE_CANCELLED, RoutingKeys.RIDE_NO_SHOW]
)
async def test_cancelled_and_no_show_free_the_driver_without_crediting_a_trip(
    event_type,
):
    driver_id = uuid4()
    repo = _driver_repo()

    async with _patched_repo(repo):
        await RideLifecycleConsumer(MagicMock()).handle(
            _envelope(
                event_type, {"driver_id": str(driver_id), "ride_id": str(uuid4())}
            )
        )

    repo.increment_total_trips.assert_not_awaited()
    repo.set_trip_status.assert_awaited_once_with(driver_id, is_on_trip=False)


@pytest.mark.asyncio
async def test_en_route_marks_driver_on_trip_without_crediting_a_trip():
    driver_id = uuid4()
    repo = _driver_repo()

    async with _patched_repo(repo):
        await RideLifecycleConsumer(MagicMock()).handle(
            _envelope(
                RoutingKeys.RIDE_DRIVER_EN_ROUTE,
                {"driver_id": str(driver_id), "ride_id": str(uuid4())},
            )
        )

    repo.set_trip_status.assert_awaited_once_with(driver_id, is_on_trip=True)
    repo.increment_total_trips.assert_not_awaited()


@pytest.mark.asyncio
async def test_rating_updates_rating_only_and_leaves_trip_count_alone():
    """A rating must not double-count the trip that ride.completed already credited."""
    driver_id = uuid4()
    repo = _driver_repo(total_trips=7, total_ratings=3)

    payload = {
        "ride_id": str(uuid4()),
        "rated_user_id": str(driver_id),
        "rated_by_user_id": str(uuid4()),
        "rating": 4,
        "rating_type": RatingType.RIDER_TO_DRIVER,
    }

    async with _patched_repo(repo):
        await RideRatingConsumer(MagicMock()).handle(
            _envelope(RoutingKeys.RIDE_RATING_SUBMITTED, payload)
        )

    repo.record_rating.assert_awaited_once_with(driver_id, 4)
    repo.increment_total_trips.assert_not_awaited()
    # The old implementation wrote total_trips through update(); nothing should now.
    repo.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_driver_to_rider_rating_does_not_touch_driver_stats():
    repo = _driver_repo()
    payload = {
        "ride_id": str(uuid4()),
        "rated_user_id": str(uuid4()),
        "rated_by_user_id": str(uuid4()),
        "rating": 5,
        "rating_type": RatingType.DRIVER_TO_RIDER,
    }

    async with _patched_repo(repo):
        await RideRatingConsumer(MagicMock()).handle(
            _envelope(RoutingKeys.RIDE_RATING_SUBMITTED, payload)
        )

    repo.record_rating.assert_not_awaited()


@pytest.mark.asyncio
async def test_event_without_driver_is_ignored():
    repo = _driver_repo()

    async with _patched_repo(repo):
        await RideLifecycleConsumer(MagicMock()).handle(
            _envelope(RoutingKeys.RIDE_COMPLETED, {"ride_id": str(uuid4())})
        )

    repo.increment_total_trips.assert_not_awaited()
    repo.set_trip_status.assert_not_awaited()
