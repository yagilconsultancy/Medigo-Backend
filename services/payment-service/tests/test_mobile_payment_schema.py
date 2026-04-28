import pytest
from pydantic import ValidationError

from app.schemas.mobile_payment import CreateMobilePaymentIntentRequest


def test_mobile_payment_request_accepts_camel_case_payload():
    body = CreateMobilePaymentIntentRequest.model_validate(
        {
            "amount": 42.75,
            "currencyCode": "cad",
            "paymentDescription": "Ride checkout",
            "orderId": "ride_123",
            "customerSessionApiVersion": "2025-09-30.clover",
            "setupFutureUsage": "off_session",
            "metadata": {
                "rideId": 123,
                "caregiver": True,
            },
        }
    )

    assert body.amount == 42.75
    assert body.currency == "CAD"
    assert body.description == "Ride checkout"
    assert body.order_id == "ride_123"
    assert body.customer_session_api_version == "2025-09-30.clover"
    assert body.setup_future_usage == "off_session"
    assert body.metadata == {
        "rideId": "123",
        "caregiver": "True",
    }


def test_mobile_payment_request_rejects_invalid_currency():
    with pytest.raises(ValidationError, match="Currency must be a 3-letter ISO code"):
        CreateMobilePaymentIntentRequest.model_validate(
            {
                "amount": 10,
                "currency": "cad$",
            }
        )
