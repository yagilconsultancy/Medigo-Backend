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
from mediride_common.schemas.enums import PaymentStatus


class _DummyPmRepo:
    async def get_by_user(self, user_id):
        return []


class _DummyTxRepo:
    def __init__(self):
        self.created = []
        self.updated = []
        self.existing = None

    async def get_by_order_id(self, order_id):
        return self.existing

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

    async def create_mobile_payment_intent(self, **kwargs):
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


@pytest.mark.asyncio
async def test_create_payment_intent_creates_pending_transaction():
    tx_repo = _DummyTxRepo()
    service = MobilePaymentService(
        pm_repo=_DummyPmRepo(),
        tx_repo=tx_repo,
        stripe_client=_DummyStripeClient(),
    )

    response = await service.create_payment_intent(
        user_id=uuid4(),
        email="rider@example.com",
        amount=25.5,
        currency="cad",
        description="Ride checkout",
        order_id="ride_123",
        metadata={"ride_id": "ride_123"},
    )

    assert response.payment_intent_id == "pi_test_123"
    assert len(tx_repo.created) == 1
    created = tx_repo.created[0]
    assert created.reference_id == "pi_test_123"
    assert created.status == PaymentStatus.PENDING
    assert created.description == "Mobile PaymentIntent order_id=ride_123"
