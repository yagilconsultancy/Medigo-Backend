import sys
from pathlib import Path
from uuid import uuid4

import pytest

sys.path.append(str(Path(__file__).resolve().parents[3] / "libs" / "common"))

from app.services.receipt_service import ReceiptService
from mediride_common.exceptions import NotFoundError


class _Repo:
    async def get_by_ride_id(self, ride_id):
        return None

    async def get_by_user(self, user_id):
        return []


class _RideClient:
    def __init__(self, ride):
        self.ride = ride

    async def get_ride(self, ride_id):
        return self.ride


def _service(rider_id, driver_id):
    ride = {
        "rider_id": str(rider_id),
        "driver_id": str(driver_id),
        "status": "completed",
        "final_fare": 30,
    }
    return ReceiptService(fare_repo=_Repo(), pm_repo=_Repo(), ride_client=_RideClient(ride))


@pytest.mark.anyio
async def test_receipt_hidden_from_unrelated_user():
    service = _service(uuid4(), uuid4())
    with pytest.raises(NotFoundError):
        await service.generate_receipt(uuid4(), uuid4())


@pytest.mark.anyio
async def test_receipt_hidden_when_ride_has_no_driver_and_viewer_is_stranger():
    ride = {"rider_id": str(uuid4()), "driver_id": None, "status": "requested"}
    service = ReceiptService(fare_repo=_Repo(), pm_repo=_Repo(), ride_client=_RideClient(ride))
    with pytest.raises(NotFoundError):
        await service.generate_receipt(uuid4(), uuid4())


@pytest.mark.anyio
async def test_receipt_available_to_rider_and_assigned_driver():
    rider, driver = uuid4(), uuid4()
    service = _service(rider, driver)
    assert (await service.generate_receipt(uuid4(), rider))["status"] == "completed"
    assert (await service.generate_receipt(uuid4(), driver))["status"] == "completed"
