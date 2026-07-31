from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.schemas.admin_driver import UpdateDriverRequest
from app.services.admin_driver_service import AdminDriverService


def _make_service(vehicle=None):
    driver_id = uuid4()

    repo = MagicMock()
    repo.get_driver_detail = AsyncMock(return_value={"user_id": driver_id})
    repo.update_user = AsyncMock()
    repo.update_driver_profile = AsyncMock()

    vehicle_repo = MagicMock()
    vehicle_repo.unassign_driver_from_all = AsyncMock()
    vehicle_repo.update = AsyncMock()
    vehicle_repo.get_by_id = AsyncMock(return_value=vehicle)

    publisher = MagicMock()
    publisher.publish = AsyncMock()

    service = AdminDriverService(
        repo=repo,
        publisher=publisher,
        auth_client=MagicMock(),
        ride_client=MagicMock(),
        vehicle_repo=vehicle_repo,
    )
    # Not under test here; both hit collaborators we've stubbed out.
    service._handle_email_change = AsyncMock()
    service.get_driver_detail = AsyncMock(return_value={"user_id": driver_id})

    return service, repo, vehicle_repo, driver_id


@pytest.mark.asyncio
async def test_gender_is_written_to_the_user_row_not_the_driver_profile():
    service, repo, _, driver_id = _make_service()

    await service.update_driver(
        driver_id, UpdateDriverRequest(gender="female", city="Toronto")
    )

    user_kwargs = repo.update_user.await_args.kwargs
    profile_kwargs = repo.update_driver_profile.await_args.kwargs
    assert user_kwargs["gender"] == "female"
    assert "gender" not in profile_kwargs
    assert profile_kwargs["city"] == "Toronto"


@pytest.mark.asyncio
async def test_assigning_a_vehicle_syncs_the_denormalized_columns():
    """Otherwise the admin detail keeps showing the previous vehicle."""
    vehicle = SimpleNamespace(
        category="wheelchair_accessible",
        make="Toyota",
        model="Sienna",
        year=2022,
        plate_number="ABCD123",
        color="Silver",
        vin="1HGCM82633A004352",
        photo_url=None,
    )
    service, repo, vehicle_repo, driver_id = _make_service(vehicle=vehicle)
    vehicle_id = uuid4()

    await service.update_driver(driver_id, UpdateDriverRequest(vehicle_id=vehicle_id))

    vehicle_repo.unassign_driver_from_all.assert_awaited_once_with(driver_id)
    vehicle_repo.update.assert_awaited_once_with(
        vehicle_id, driver_profile_id=driver_id
    )
    profile_kwargs = repo.update_driver_profile.await_args.kwargs
    assert profile_kwargs["vehicle_make"] == "Toyota"
    assert profile_kwargs["vehicle_model"] == "Sienna"
    assert profile_kwargs["vehicle_plate"] == "ABCD123"
    assert profile_kwargs["vehicle_year"] == 2022


@pytest.mark.asyncio
async def test_explicit_null_vehicle_id_unassigns_and_clears_the_columns():
    service, repo, vehicle_repo, driver_id = _make_service()

    await service.update_driver(driver_id, UpdateDriverRequest(vehicle_id=None))

    vehicle_repo.unassign_driver_from_all.assert_awaited_once_with(driver_id)
    vehicle_repo.update.assert_not_awaited()
    profile_kwargs = repo.update_driver_profile.await_args.kwargs
    assert profile_kwargs["vehicle_make"] is None
    assert profile_kwargs["vehicle_plate"] is None


@pytest.mark.asyncio
async def test_omitting_vehicle_id_leaves_the_vehicle_alone():
    service, repo, vehicle_repo, driver_id = _make_service()

    await service.update_driver(driver_id, UpdateDriverRequest(city="Ottawa"))

    vehicle_repo.unassign_driver_from_all.assert_not_awaited()
    profile_kwargs = repo.update_driver_profile.await_args.kwargs
    assert "vehicle_make" not in profile_kwargs


@pytest.mark.asyncio
async def test_explicit_vehicle_fields_win_over_the_synced_snapshot():
    """An admin can still correct a driver whose vehicle isn't in the fleet."""
    vehicle = SimpleNamespace(
        category="standard",
        make="Toyota",
        model="Sienna",
        year=2022,
        plate_number="ABCD123",
        color="Silver",
        vin=None,
        photo_url=None,
    )
    service, repo, _, driver_id = _make_service(vehicle=vehicle)

    await service.update_driver(
        driver_id,
        UpdateDriverRequest(vehicle_id=uuid4(), vehicle_plate="OVERRIDE1"),
    )

    profile_kwargs = repo.update_driver_profile.await_args.kwargs
    assert profile_kwargs["vehicle_plate"] == "OVERRIDE1"
    # The rest of the snapshot still applies.
    assert profile_kwargs["vehicle_make"] == "Toyota"


@pytest.mark.asyncio
async def test_new_personal_fields_reach_the_driver_profile():
    service, repo, _, driver_id = _make_service()

    await service.update_driver(
        driver_id,
        UpdateDriverRequest(
            emergency_contact_name="Grace Hopper",
            emergency_contact_phone="+14165550123",
            address="1 Queen St W",
            city="Toronto",
            province="ON",
            postal_code="M5H 2N2",
            notes="Prefers morning shifts",
            account_status="active",
        ),
    )

    profile_kwargs = repo.update_driver_profile.await_args.kwargs
    assert profile_kwargs["emergency_contact_name"] == "Grace Hopper"
    assert profile_kwargs["address"] == "1 Queen St W"
    assert profile_kwargs["postal_code"] == "M5H 2N2"
    assert profile_kwargs["notes"] == "Prefers morning shifts"
    assert profile_kwargs["account_status"] == "active"
