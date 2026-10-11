from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.api.v1 import ride_endpoints, safety_endpoints
from mediride_common.auth.models import UserClaims
from mediride_common.exceptions import NotFoundError, ValidationError
from mediride_common.schemas.enums import UserRole


def _ride(rider, driver=None):
    return SimpleNamespace(rider_id=rider, driver_id=driver, caregiver_id=None)


def _patch_ride(monkeypatch, ride):
    repo = SimpleNamespace(get_by_id=AsyncMock(return_value=ride))
    monkeypatch.setattr(safety_endpoints, "RideRepository", lambda session: repo)
    created = SimpleNamespace(create=AsyncMock(side_effect=lambda r: r))
    monkeypatch.setattr(safety_endpoints, "SafetyReportRepository", lambda s: created)
    monkeypatch.setattr(
        safety_endpoints.SafetyReportResponse, "model_validate", staticmethod(lambda r: r)
    )
    return created


def _body(ride_id, reported=None):
    return SimpleNamespace(
        ride_id=ride_id,
        reported_user_id=reported,
        report_type="other",
        description="x",
    )


@pytest.mark.asyncio
async def test_report_about_a_ride_you_were_not_on_is_refused(monkeypatch):
    _patch_ride(monkeypatch, _ride(uuid4(), uuid4()))
    stranger = UserClaims(id=uuid4(), role=UserRole.RIDER)
    with pytest.raises(NotFoundError):
        await safety_endpoints.create_safety_report(_body(uuid4()), stranger, MagicMock())


@pytest.mark.asyncio
async def test_report_must_name_someone_on_the_ride(monkeypatch):
    rider = UserClaims(id=uuid4(), role=UserRole.RIDER)
    _patch_ride(monkeypatch, _ride(rider.id, uuid4()))
    with pytest.raises(ValidationError):
        await safety_endpoints.create_safety_report(
            _body(uuid4(), reported=uuid4()), rider, MagicMock()
        )


@pytest.mark.asyncio
async def test_valid_report_about_the_driver_is_saved(monkeypatch):
    rider = UserClaims(id=uuid4(), role=UserRole.RIDER)
    driver = uuid4()
    created = _patch_ride(monkeypatch, _ride(rider.id, driver))
    await safety_endpoints.create_safety_report(
        _body(uuid4(), reported=driver), rider, MagicMock()
    )
    created.create.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role,expected_business", [(UserRole.RIDER, None), (UserRole.BUSINESS, "fleet")]
)
async def test_only_a_rider_is_stopped_from_choosing_a_fleet(
    monkeypatch, role, expected_business
):
    fleet = uuid4()
    request = SimpleNamespace(
        model_dump=lambda: {"business_id": fleet, "booking_channel": "mobile_app"}
    )
    service = SimpleNamespace(create_ride=AsyncMock(return_value=SimpleNamespace()))
    monkeypatch.setattr(
        ride_endpoints.RideResponse, "model_validate", staticmethod(lambda r: r)
    )
    user = UserClaims(id=uuid4(), role=role)
    await ride_endpoints.create_ride(request, user, service)
    sent = service.create_ride.await_args.kwargs["business_id"]
    assert sent == (None if expected_business is None else fleet)
