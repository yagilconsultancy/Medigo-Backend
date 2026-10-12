from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.schemas.ride import PublicTripViewResponse
from app.services.ride_service import RideService
from mediride_common.exceptions import NotFoundError
from mediride_common.schemas.enums import RideStatus

NOW = datetime.now(timezone.utc)


def _ride(status, **extra):
    base = dict(
        id=uuid4(),
        status=status,
        driver_id=uuid4(),
        rider_id=uuid4(),
        pickup_address="1 Start St",
        destination_address="2 End Ave",
        pickup_latitude=43.0,
        pickup_longitude=-81.0,
        destination_latitude=43.1,
        destination_longitude=-81.1,
        scheduled_at=NOW,
        dropoff_at=None,
        cancelled_at=None,
        updated_at=NOW,
        # Things that must never reach a link holder:
        special_instructions="medical secret",
        estimated_fare=55.0,
        passenger_phone="555-0100",
    )
    base.update(extra)
    return SimpleNamespace(**base)


def _service(ride, driver=None, location=None):
    service = RideService.__new__(RideService)
    service.ride_repo = MagicMock()
    service.ride_repo.get_by_share_token = AsyncMock(return_value=ride)
    service.user_client = MagicMock()
    service.user_client.get_driver_profile = AsyncMock(
        return_value=driver
        or {
            "first_name": "Sam",
            "last_name": "Driver",
            "phone": "555-0199",
            "vehicle_make": "Toyota",
            "vehicle_model": "Sienna",
            "vehicle_color": "Blue",
            "vehicle_plate": "ABC123",
        }
    )
    service.tracking_client = MagicMock()
    service.tracking_client.get_driver_location = AsyncMock(
        return_value=location or {"latitude": 43.05, "longitude": -81.05}
    )
    return service


@pytest.mark.asyncio
async def test_unknown_token_is_not_found():
    service = _service(None)
    with pytest.raises(NotFoundError):
        await service.get_public_trip_view("nope")


@pytest.mark.asyncio
async def test_link_one_hour_after_the_ride_ended_is_not_found():
    ride = _ride(
        RideStatus.COMPLETED, dropoff_at=NOW - timedelta(hours=2), updated_at=NOW - timedelta(hours=2)
    )
    with pytest.raises(NotFoundError):
        await _service(ride).get_public_trip_view("t")


@pytest.mark.asyncio
async def test_active_ride_shows_driver_first_name_vehicle_and_position_only():
    view = await _service(_ride(RideStatus.IN_PROGRESS)).get_public_trip_view("t")
    assert view["ended"] is False
    assert view["driver"] == {
        "first_name": "Sam",
        "vehicle_make": "Toyota",
        "vehicle_model": "Sienna",
        "vehicle_color": "Blue",
        "vehicle_plate": "ABC123",
    }
    assert view["driver_location"] == {"latitude": 43.05, "longitude": -81.05}


@pytest.mark.asyncio
async def test_response_never_contains_private_fields():
    view = await _service(_ride(RideStatus.DRIVER_EN_ROUTE)).get_public_trip_view("t")
    payload = PublicTripViewResponse(**view).model_dump(mode="json")
    text = str(payload)
    for secret in ("medical secret", "555-0100", "555-0199", "Driver", "55.0"):
        assert secret not in text
    for key in ("rider_id", "driver_id", "estimated_fare", "passenger_phone", "special_instructions", "id"):
        assert key not in payload


@pytest.mark.asyncio
async def test_not_started_ride_has_no_driver_or_position():
    service = _service(_ride(RideStatus.CONFIRMED))
    view = await service.get_public_trip_view("t")
    assert view["driver"] is None and view["driver_location"] is None
    service.tracking_client.get_driver_location.assert_not_called()


@pytest.mark.asyncio
async def test_finished_ride_within_the_hour_hides_driver_and_position():
    ride = _ride(RideStatus.COMPLETED, dropoff_at=NOW - timedelta(minutes=10))
    service = _service(ride)
    view = await service.get_public_trip_view("t")
    assert view["ended"] is True
    assert view["driver"] is None and view["driver_location"] is None
    service.tracking_client.get_driver_location.assert_not_called()


@pytest.mark.asyncio
async def test_missing_gps_gives_no_position_but_still_works():
    service = _service(_ride(RideStatus.DRIVER_ARRIVED))
    service.tracking_client.get_driver_location = AsyncMock(return_value=None)
    view = await service.get_public_trip_view("t")
    assert view["driver"] is not None and view["driver_location"] is None
