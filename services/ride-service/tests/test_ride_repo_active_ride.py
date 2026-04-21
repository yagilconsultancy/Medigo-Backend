from uuid import uuid4

import pytest

from app.models.ride import Ride
from app.repositories.ride_repo import RideRepository
from mediride_common.schemas.enums import RideStatus


class FakeScalars:
    def __init__(self, rows):
        self.rows = rows

    def first(self):
        return self.rows[0] if self.rows else None


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return FakeScalars(self.rows)

    def scalar_one_or_none(self):
        raise AssertionError("active ride queries must tolerate multiple rows")


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return FakeResult(self.rows)


@pytest.mark.asyncio
async def test_get_active_ride_for_rider_returns_first_match_without_multiple_rows_error():
    expected = Ride(id=uuid4(), rider_id=uuid4(), status=RideStatus.IN_PROGRESS)
    session = FakeSession([expected, Ride(id=uuid4(), rider_id=expected.rider_id)])

    ride = await RideRepository(session).get_active_ride_for_rider(expected.rider_id)

    assert ride is expected
    assert session.statement._limit_clause.value == 1


@pytest.mark.asyncio
async def test_get_active_ride_for_driver_returns_first_match_without_multiple_rows_error():
    expected = Ride(id=uuid4(), driver_id=uuid4(), status=RideStatus.DRIVER_EN_ROUTE)
    session = FakeSession([expected, Ride(id=uuid4(), driver_id=expected.driver_id)])

    ride = await RideRepository(session).get_active_ride_for_driver(expected.driver_id)

    assert ride is expected
    assert session.statement._limit_clause.value == 1
