from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[3] / "libs" / "common"))

from app.services.receipt_service import ReceiptService


class DummyFareRepo:
    def __init__(self, breakdown):
        self.breakdown = breakdown

    async def get_by_ride_id(self, ride_id):
        return self.breakdown


class DummyPaymentMethodRepo:
    def __init__(self, methods):
        self.methods = methods
        self.calls = []

    async def get_by_user(self, user_id):
        self.calls.append(user_id)
        return self.methods


class DummyRideClient:
    def __init__(self, ride_data):
        self.ride_data = ride_data

    async def get_ride(self, ride_id):
        return self.ride_data


@pytest.mark.anyio
async def test_generate_receipt_for_rider_uses_total_fare_and_payment_method():
    ride_id = uuid4()
    rider_id = uuid4()
    driver_id = uuid4()
    breakdown = SimpleNamespace(
        distance_km=12.5,
        base_fare=20,
        distance_charge=10,
        medical_assist_premium=5,
        service_fee=2,
        wait_time_minutes=None,
        wait_time_charge=None,
        surcharges_total=None,
        surcharges_capped=None,
        surcharge_details=None,
        highway_407_toll=None,
        insurance_gateway_fee=None,
        flat_surcharge=None,
        platform_fee=8,
        total_fare=45,
        driver_earnings=37,
        is_dialysis_rate=False,
        rate_card_version=1,
    )
    payment_method = SimpleNamespace(is_default=True, method_type="visa", last_four="4242")
    service = ReceiptService(
        fare_repo=DummyFareRepo(breakdown),
        pm_repo=DummyPaymentMethodRepo([payment_method]),
        ride_client=DummyRideClient(
            {
                "rider_id": str(rider_id),
                "driver_id": str(driver_id),
                "scheduled_at": "2026-07-10T09:00:00Z",
                "pickup_address": "1 Main St",
                "destination_address": "2 Elm St",
                "estimated_distance_miles": 8,
                "estimated_duration_minutes": 20,
                "status": "completed",
            }
        ),
    )

    receipt = await service.generate_receipt(ride_id, rider_id)

    assert receipt["total_fare"] == 45.0
    assert receipt["driver_earnings"] == 37.0
    assert receipt["payment_method_type"] == "visa"
    assert receipt["payment_method_last_four"] == "4242"


@pytest.mark.anyio
async def test_generate_receipt_for_driver_uses_driver_earnings():
    ride_id = uuid4()
    rider_id = uuid4()
    driver_id = uuid4()
    breakdown = SimpleNamespace(
        distance_km=12.5,
        base_fare=20,
        distance_charge=10,
        medical_assist_premium=5,
        service_fee=2,
        wait_time_minutes=None,
        wait_time_charge=None,
        surcharges_total=None,
        surcharges_capped=None,
        surcharge_details=None,
        highway_407_toll=None,
        insurance_gateway_fee=None,
        flat_surcharge=None,
        platform_fee=8,
        total_fare=45,
        driver_earnings=37,
        is_dialysis_rate=False,
        rate_card_version=1,
    )
    pm_repo = DummyPaymentMethodRepo([])
    service = ReceiptService(
        fare_repo=DummyFareRepo(breakdown),
        pm_repo=pm_repo,
        ride_client=DummyRideClient(
            {
                "rider_id": str(rider_id),
                "driver_id": str(driver_id),
                "scheduled_at": "2026-07-10T09:00:00Z",
                "pickup_address": "1 Main St",
                "destination_address": "2 Elm St",
                "estimated_distance_miles": 8,
                "estimated_duration_minutes": 20,
                "status": "completed",
            }
        ),
    )

    receipt = await service.generate_receipt(ride_id, driver_id)

    assert receipt["total_fare"] == 37.0
    assert receipt["driver_earnings"] == 37.0
    assert receipt["payment_method_type"] == ""
    assert receipt["payment_method_last_four"] == ""
    assert pm_repo.calls == []