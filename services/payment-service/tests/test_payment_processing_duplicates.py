"""A ride must never be charged twice, and the driver credited only once."""
import os
import sys
import types
from types import SimpleNamespace
from uuid import uuid4

import pytest

os.environ["DEBUG"] = "false"
os.environ["ENVIRONMENT"] = "development"

stripe_stub = types.ModuleType("stripe")
stripe_stub.error = types.SimpleNamespace(StripeError=Exception, CardError=Exception)
sys.modules.setdefault("stripe", stripe_stub)

from app.services import payment_processing_service as pps
from mediride_common.schemas.enums import PaymentStatus, TransactionType


class _TxRepo:
    def __init__(self, existing=None):
        self.rows = list(existing or [])

    async def get_by_ride_id(self, ride_id):
        return list(self.rows)

    async def create(self, tx):
        tx.id = tx.id or uuid4()  # the database assigns this in real use
        self.rows.append(tx)
        return tx


class _Earnings:
    def __init__(self):
        self.credits = []

    async def add_earnings(self, driver_id, amount):
        self.credits.append((driver_id, amount))


class _Stripe:
    def __init__(self):
        self.purchases = 0

    async def purchase(self, **kwargs):
        self.purchases += 1
        return SimpleNamespace(
            success=True, transaction_id="pi_x", reference_number="ch_x",
            response_code="succeeded", message="ok",
        )


class _PmRepo:
    async def get_by_user(self, user_id):
        return [SimpleNamespace(is_default=True, external_id="pm_1", stripe_customer_id="cus_1")]


class _Rides:
    def __init__(self):
        self.fare_updates = []

    async def get_ride(self, ride_id):
        return {"ride_type": "ambulatory"}

    async def update_ride_fare(self, ride_id, fare):
        self.fare_updates.append(fare)
        return True


class _Publisher:
    async def publish(self, *args, **kwargs):
        pass


class _FakeFareService:
    def __init__(self, **kwargs):
        pass

    async def calculate_fare(self, data):
        return SimpleNamespace(total_fare=40.0, driver_earnings=30.0)


def _service(tx_repo, monkeypatch):
    monkeypatch.setattr(pps, "FareService", _FakeFareService)
    stripe, earnings, rides = _Stripe(), _Earnings(), _Rides()
    service = pps.PaymentProcessingService(
        tx_repo=tx_repo, fare_repo=None, pm_repo=_PmRepo(), earnings_repo=earnings,
        rate_card_repo=None, holiday_repo=None, weather_repo=None, dialysis_repo=None,
        stripe_client=stripe, ride_client=rides, publisher=_Publisher(),
    )
    return service, stripe, earnings, rides


def _paid(rider, ride):
    return SimpleNamespace(
        id=uuid4(), ride_id=ride, user_id=rider, description="Mobile PaymentIntent",
        transaction_type=TransactionType.RIDE_PAYMENT, status=PaymentStatus.COMPLETED,
    )


@pytest.mark.asyncio
async def test_prepaid_ride_is_not_charged_again_but_driver_is_credited(monkeypatch):
    ride, rider, driver = uuid4(), uuid4(), uuid4()
    paid = _paid(rider, ride)
    service, stripe, earnings, _ = _service(_TxRepo([paid]), monkeypatch)

    result = await service.process_ride_payment(ride, rider, driver)

    assert result is paid
    assert stripe.purchases == 0
    assert earnings.credits == [(driver, 30.0)]


@pytest.mark.asyncio
async def test_event_delivered_twice_credits_driver_once(monkeypatch):
    ride, rider, driver = uuid4(), uuid4(), uuid4()
    repo = _TxRepo([_paid(rider, ride)])
    service, stripe, earnings, _ = _service(repo, monkeypatch)

    await service.process_ride_payment(ride, rider, driver)
    await service.process_ride_payment(ride, rider, driver)

    assert stripe.purchases == 0
    assert earnings.credits == [(driver, 30.0)]


@pytest.mark.asyncio
async def test_unpaid_ride_is_charged_once_and_redelivery_does_not_charge_again(monkeypatch):
    ride, rider, driver = uuid4(), uuid4(), uuid4()
    repo = _TxRepo()
    service, stripe, earnings, rides = _service(repo, monkeypatch)

    await service.process_ride_payment(ride, rider, driver)
    await service.process_ride_payment(ride, rider, driver)

    assert stripe.purchases == 1
    assert earnings.credits == [(driver, 30.0)]
    assert rides.fare_updates == [40.0]


@pytest.mark.asyncio
async def test_other_riders_payment_does_not_count(monkeypatch):
    ride, rider, driver = uuid4(), uuid4(), uuid4()
    service, stripe, _, _ = _service(_TxRepo([_paid(uuid4(), ride)]), monkeypatch)

    await service.process_ride_payment(ride, rider, driver)

    assert stripe.purchases == 1
