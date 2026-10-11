from types import SimpleNamespace
from uuid import uuid4
import os
import sys
import types

import pytest

os.environ["DEBUG"] = "false"
os.environ["ENVIRONMENT"] = "development"

stripe_stub = types.ModuleType("stripe")
stripe_stub.error = types.SimpleNamespace(StripeError=Exception, CardError=Exception)
sys.modules.setdefault("stripe", stripe_stub)

from app.services.mobile_payment_service import MobilePaymentService
from mediride_common.exceptions import ConflictError, NotFoundError, ValidationError
from mediride_common.schemas.enums import PaymentStatus, TransactionType


class _DummyPmRepo:
    async def get_by_user(self, user_id):
        return []


class _DummyTxRepo:
    def __init__(self):
        self.created = []
        self.updated = []
        self.existing = None
        self.by_ride = []

    async def get_by_order_id(self, order_id):
        return self.existing

    async def get_by_ride_id(self, ride_id):
        return self.by_ride

    async def create(self, transaction):
        self.created.append(transaction)
        return transaction

    async def update(self, transaction, **kwargs):
        self.updated.append((transaction, kwargs))
        for key, value in kwargs.items():
            setattr(transaction, key, value)
        return transaction


class _DummyStripeClient:
    publishable_key = "pk_test_123"

    def __init__(self):
        self.calls = []

    async def create_mobile_payment_intent(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            success=True,
            payment_intent_id="pi_test_123",
            client_secret="pi_test_123_secret",
            customer_id="cus_test_123",
            ephemeral_key_secret="eph_test_123",
            publishable_key="pk_test_123",
            amount=kwargs["amount"],
            currency=str(kwargs["currency"]).upper(),
            message="ok",
        )


class _DummyRideClient:
    def __init__(self, ride):
        self.ride = ride

    async def get_ride(self, ride_id):
        return self.ride


def _ride(rider_id, **overrides):
    ride = {
        "id": str(RIDE_ID),
        "rider_id": str(rider_id),
        "caregiver_id": None,
        "status": "pending",
        "estimated_fare": 40.0,
        "final_fare": None,
    }
    ride.update(overrides)
    return ride


RIDE_ID = uuid4()


def _service(ride, tx_repo=None, stripe=None):
    tx_repo = tx_repo or _DummyTxRepo()
    stripe = stripe or _DummyStripeClient()
    return (
        MobilePaymentService(
            pm_repo=_DummyPmRepo(),
            tx_repo=tx_repo,
            stripe_client=stripe,
            ride_client=_DummyRideClient(ride),
        ),
        tx_repo,
        stripe,
    )


async def _pay(service, user_id, amount=40.0, order_id=None):
    return await service.create_payment_intent(
        user_id=user_id,
        email="rider@example.com",
        amount=amount,
        currency="cad",
        description="Ride checkout",
        order_id=order_id or str(RIDE_ID),
    )


@pytest.mark.asyncio
async def test_create_payment_intent_creates_pending_transaction():
    rider = uuid4()
    service, tx_repo, _ = _service(_ride(rider))

    response = await _pay(service, rider)

    assert response.payment_intent_id == "pi_test_123"
    assert len(tx_repo.created) == 1
    created = tx_repo.created[0]
    assert created.reference_id == "pi_test_123"
    assert created.status == PaymentStatus.PENDING
    assert created.description == f"Mobile PaymentIntent order_id={RIDE_ID}"


@pytest.mark.asyncio
async def test_amount_comes_from_the_ride_not_the_request():
    rider = uuid4()
    service, tx_repo, stripe = _service(_ride(rider, estimated_fare=40.0))

    response = await _pay(service, rider, amount=0.01)

    assert stripe.calls[0]["amount"] == 40.0
    assert tx_repo.created[0].amount == 40.0
    assert response.amount == 40.0


@pytest.mark.asyncio
async def test_completed_ride_uses_final_fare():
    rider = uuid4()
    service, _, stripe = _service(
        _ride(rider, status="completed", estimated_fare=40.0, final_fare=52.5)
    )

    await _pay(service, rider, amount=40.0)

    assert stripe.calls[0]["amount"] == 52.5


@pytest.mark.asyncio
async def test_caregiver_may_pay():
    rider, caregiver = uuid4(), uuid4()
    service, _, stripe = _service(_ride(rider, caregiver_id=str(caregiver)))

    await _pay(service, caregiver)

    assert len(stripe.calls) == 1


@pytest.mark.asyncio
async def test_other_user_gets_not_found_and_stripe_is_not_called():
    service, tx_repo, stripe = _service(_ride(uuid4()))

    with pytest.raises(NotFoundError):
        await _pay(service, uuid4())

    assert stripe.calls == []
    assert tx_repo.created == []


@pytest.mark.asyncio
async def test_missing_ride_is_not_found():
    service, _, stripe = _service(None)

    with pytest.raises(NotFoundError):
        await _pay(service, uuid4())

    assert stripe.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["cancelled", "no_show"])
async def test_cancelled_ride_cannot_be_paid(status):
    rider = uuid4()
    service, _, stripe = _service(_ride(rider, status=status))

    with pytest.raises(ConflictError):
        await _pay(service, rider)

    assert stripe.calls == []


@pytest.mark.asyncio
async def test_already_paid_ride_is_refused_and_not_reset():
    rider = uuid4()
    paid = SimpleNamespace(
        transaction_type=TransactionType.RIDE_PAYMENT,
        status=PaymentStatus.COMPLETED,
        user_id=rider,
    )
    service, tx_repo, stripe = _service(_ride(rider))
    tx_repo.by_ride = [paid]
    tx_repo.existing = paid

    with pytest.raises(ConflictError):
        await _pay(service, rider)

    assert stripe.calls == []
    assert tx_repo.updated == []
    assert paid.status == PaymentStatus.COMPLETED


@pytest.mark.asyncio
async def test_refunded_payment_does_not_block_a_new_payment():
    rider = uuid4()
    refunded = SimpleNamespace(
        transaction_type=TransactionType.RIDE_PAYMENT,
        status=PaymentStatus.REFUNDED,
        user_id=rider,
    )
    service, tx_repo, stripe = _service(_ride(rider))
    tx_repo.by_ride = [refunded]

    await _pay(service, rider)

    assert len(stripe.calls) == 1


@pytest.mark.asyncio
async def test_pending_transaction_is_reused_for_a_retry():
    rider = uuid4()
    pending = SimpleNamespace(status=PaymentStatus.PENDING)
    service, tx_repo, _ = _service(_ride(rider))
    tx_repo.existing = pending

    await _pay(service, rider)

    assert tx_repo.created == []
    assert pending.reference_id == "pi_test_123"


@pytest.mark.asyncio
async def test_missing_stored_fare_falls_back_to_requested_amount():
    rider = uuid4()
    service, _, stripe = _service(_ride(rider, estimated_fare=None))

    await _pay(service, rider, amount=33.0)

    assert stripe.calls[0]["amount"] == 33.0


@pytest.mark.asyncio
async def test_same_request_twice_uses_the_same_idempotency_key():
    rider = uuid4()
    service, _, stripe = _service(_ride(rider))

    await _pay(service, rider)
    await _pay(service, rider)

    assert stripe.calls[0]["idempotency_key"] == stripe.calls[1]["idempotency_key"]
    assert stripe.calls[0]["idempotency_key"].startswith("mobile-pi-")


@pytest.mark.asyncio
async def test_invalid_order_id_is_rejected_before_anything_else():
    service, _, stripe = _service(_ride(uuid4()))

    with pytest.raises(ValidationError):
        await _pay(service, uuid4(), order_id="ride_123")

    assert stripe.calls == []
