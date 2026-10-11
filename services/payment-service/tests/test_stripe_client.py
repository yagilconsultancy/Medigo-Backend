import pytest

pytest.importorskip("stripe")

from app.clients.stripe_client import StripeClient


@pytest.mark.asyncio
async def test_tokenize_card_uses_mock_when_stripe_key_missing_in_development():
    client = StripeClient(
        secret_key="",
        environment="development",
        mock_in_development=True,
    )

    result = await client.tokenize_card(
        holder_name="Test Card",
        stripe_token="tok_visa",
        user_id="47d71b6d-dd77-4d27-9c7c-531accb515b1",
    )

    assert result.success is True
    assert result.data_key is not None
    assert result.data_key.startswith("pm_mock_")
    assert result.customer_id == "cus_mock_47d71b6ddd774d279c7c531a"
    assert result.last_four == "0000"
    assert result.brand == "Mock"


@pytest.mark.asyncio
async def test_tokenize_card_does_not_mock_when_disabled():
    client = StripeClient(
        secret_key="",
        environment="development",
        mock_in_development=False,
    )

    result = await client.tokenize_card(
        holder_name="Test Card",
        stripe_token="tok_visa",
        user_id="47d71b6d-dd77-4d27-9c7c-531accb515b1",
    )

    assert result.success is False
    assert result.message == "Stripe is not configured"


@pytest.mark.asyncio
async def test_mock_payment_method_can_be_used_for_local_purchase_lifecycle():
    client = StripeClient(
        secret_key="",
        environment="development",
        mock_in_development=True,
    )

    purchase = await client.purchase(
        order_id="ride-1",
        amount=25.50,
        data_key="pm_mock_abc123",
        customer_id="cus_mock_user123",
    )
    preauth = await client.preauth(
        order_id="ride-1",
        amount=25.50,
        data_key="pm_mock_abc123",
        customer_id="cus_mock_user123",
    )
    capture = await client.capture(
        order_id="ride-1",
        transaction_id=preauth.transaction_id,
        amount=25.50,
    )
    void = await client.void(order_id="ride-1", transaction_id=preauth.transaction_id)

    assert purchase.success is True
    assert purchase.response_code == "succeeded"
    assert preauth.success is True
    assert preauth.response_code == "requires_capture"
    assert capture.success is True
    assert capture.response_code == "succeeded"
    assert void.success is True
    assert void.response_code == "canceled"


def test_mock_ids_are_ignored_outside_development():
    client = StripeClient(
        secret_key="",
        environment="production",
        mock_in_development=True,
    )

    assert client._is_mock_payment_method("pm_mock_abc123", "cus_mock_user123") is False
    assert client._is_mock_transaction("pi_mock_abc123") is False
