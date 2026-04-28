import importlib
import sys
import types

import pytest


class DummyStripeError(Exception):
    pass


stripe_stub = types.ModuleType("stripe")
stripe_stub.api_key = None
stripe_stub.error = types.SimpleNamespace(StripeError=DummyStripeError, CardError=DummyStripeError)


class CustomerAPI:
    create_calls = []

    @staticmethod
    async def create_async(**kwargs):
        CustomerAPI.create_calls.append(kwargs)
        return types.SimpleNamespace(id="cus_test_123")


class PaymentIntentAPI:
    create_calls = []

    @staticmethod
    async def create_async(**kwargs):
        PaymentIntentAPI.create_calls.append(kwargs)
        return types.SimpleNamespace(
            id="pi_test_123",
            client_secret="pi_test_123_secret_abc",
        )


class EphemeralKeyAPI:
    create_calls = []

    @staticmethod
    async def create_async(**kwargs):
        EphemeralKeyAPI.create_calls.append(kwargs)
        return types.SimpleNamespace(secret="ephkey_test_123")


class PaymentMethodAPI:
    retrieve_calls = []
    attach_calls = []

    @staticmethod
    async def retrieve_async(payment_method_id):
        PaymentMethodAPI.retrieve_calls.append(payment_method_id)
        return types.SimpleNamespace(id=payment_method_id, customer="cus_existing_123")

    @staticmethod
    async def attach_async(payment_method_id, **kwargs):
        PaymentMethodAPI.attach_calls.append((payment_method_id, kwargs))
        return types.SimpleNamespace(id=payment_method_id, customer=kwargs.get("customer"))


stripe_stub.Customer = CustomerAPI
stripe_stub.PaymentIntent = PaymentIntentAPI
stripe_stub.EphemeralKey = EphemeralKeyAPI
stripe_stub.PaymentMethod = PaymentMethodAPI

sys.modules["stripe"] = stripe_stub
stripe_client_module = importlib.import_module("app.clients.stripe_client")
stripe_client_module = importlib.reload(stripe_client_module)
StripeClient = stripe_client_module.StripeClient


@pytest.mark.asyncio
async def test_create_mobile_payment_intent_returns_client_secret_and_ephemeral_key():
    CustomerAPI.create_calls.clear()
    PaymentIntentAPI.create_calls.clear()
    EphemeralKeyAPI.create_calls.clear()

    client = StripeClient(
        secret_key="sk_test_123",
        publishable_key="pk_test_123",
        environment="development",
        mock_in_development=True,
    )

    result = await client.create_mobile_payment_intent(
        user_id="user_123",
        email="rider@example.com",
        amount=24.5,
        currency="cad",
        description="Ride payment",
        metadata={"ride_id": "ride_123"},
        customer_session_api_version="2025-09-30.clover",
        setup_future_usage="off_session",
    )

    assert result.success is True
    assert result.payment_intent_id == "pi_test_123"
    assert result.client_secret == "pi_test_123_secret_abc"
    assert result.customer_id == "cus_test_123"
    assert result.ephemeral_key_secret == "ephkey_test_123"
    assert result.publishable_key == "pk_test_123"
    assert result.currency == "CAD"
    assert CustomerAPI.create_calls[0]["email"] == "rider@example.com"
    assert PaymentIntentAPI.create_calls[0]["amount"] == 2450
    assert PaymentIntentAPI.create_calls[0]["currency"] == "cad"
    assert PaymentIntentAPI.create_calls[0]["automatic_payment_methods"] == {"enabled": True}
    assert EphemeralKeyAPI.create_calls[0]["customer"] == "cus_test_123"
    assert EphemeralKeyAPI.create_calls[0]["stripe_version"] == "2025-09-30.clover"


@pytest.mark.asyncio
async def test_tokenize_card_reuses_customer_attached_to_payment_method():
    PaymentMethodAPI.retrieve_calls.clear()
    PaymentMethodAPI.attach_calls.clear()
    CustomerAPI.create_calls.clear()

    client = StripeClient(
        secret_key="sk_test_123",
        publishable_key="pk_test_123",
        environment="development",
        mock_in_development=True,
    )

    result = await client.tokenize_card(
        holder_name="Test Card",
        stripe_payment_method_id="pm_123",
        user_id="user_123",
        existing_customer_id=None,
    )

    assert result.success is True
    assert result.data_key == "pm_123"
    assert result.customer_id == "cus_existing_123"
    assert CustomerAPI.create_calls == []
    assert PaymentMethodAPI.retrieve_calls == ["pm_123"]
    assert PaymentMethodAPI.attach_calls == []


@pytest.mark.asyncio
async def test_create_mobile_payment_intent_requires_publishable_key():
    client = StripeClient(
        secret_key="sk_test_123",
        publishable_key="",
        environment="development",
        mock_in_development=True,
    )

    result = await client.create_mobile_payment_intent(
        user_id="user_123",
        amount=10,
    )

    assert result.success is False
    assert result.message == "Stripe mobile SDK setup requires STRIPE_PUBLISHABLE_KEY"
