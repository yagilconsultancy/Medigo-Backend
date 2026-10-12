from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.ride_service import share_link_expired
from mediride_common.schemas.enums import RideStatus

NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)


def _ride(status, dropoff_at=None, cancelled_at=None, updated_at=None):
    return SimpleNamespace(
        status=status,
        dropoff_at=dropoff_at,
        cancelled_at=cancelled_at,
        updated_at=updated_at,
    )


def test_active_rides_keep_a_working_link():
    for status in (
        RideStatus.REQUESTED,
        RideStatus.DRIVER_ASSIGNED,
        RideStatus.DRIVER_EN_ROUTE,
        RideStatus.IN_PROGRESS,
    ):
        assert share_link_expired(_ride(status, updated_at=NOW - timedelta(days=3)), NOW) is False


def test_completed_ride_link_works_for_one_hour():
    ride = _ride(RideStatus.COMPLETED, dropoff_at=NOW - timedelta(minutes=59))
    assert share_link_expired(ride, NOW) is False


def test_completed_ride_link_stops_after_one_hour():
    ride = _ride(RideStatus.COMPLETED, dropoff_at=NOW - timedelta(minutes=61))
    assert share_link_expired(ride, NOW) is True


def test_cancelled_ride_uses_cancel_time():
    ride = _ride(
        RideStatus.CANCELLED,
        cancelled_at=NOW - timedelta(hours=2),
        updated_at=NOW,
    )
    assert share_link_expired(ride, NOW) is True


def test_falls_back_to_updated_at_and_handles_naive_times():
    ride = _ride(RideStatus.NO_SHOW, updated_at=(NOW - timedelta(hours=3)).replace(tzinfo=None))
    assert share_link_expired(ride, NOW) is True
