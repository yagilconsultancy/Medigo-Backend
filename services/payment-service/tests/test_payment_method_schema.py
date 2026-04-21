import pytest
from pydantic import ValidationError

from app.schemas.payment_method import AddPaymentMethodRequest


def test_payment_method_request_accepts_stripe_token_payload():
    body = AddPaymentMethodRequest.model_validate(
        {
            "method_type": "card",
            "stripe_token": "tok_visa",
            "holder_name": "Test Card",
        }
    )

    assert body.method_type == "card"
    assert body.stripe_token == "tok_visa"
    assert body.holder_name == "Test Card"


def test_payment_method_request_accepts_mobile_camel_case_token_payload():
    body = AddPaymentMethodRequest.model_validate(
        {
            "type": "card",
            "stripeToken": "tok_visa",
            "holderName": "Test Card",
        }
    )

    assert body.method_type == "card"
    assert body.stripe_token == "tok_visa"
    assert body.holder_name == "Test Card"


def test_payment_method_request_rejects_raw_card_fields():
    with pytest.raises(ValidationError, match="Raw card fields are not accepted"):
        AddPaymentMethodRequest.model_validate(
            {
                "type": "card",
                "cardNumber": "4242424242424242",
                "expiryDate": "04/28",
                "cvv": "123",
                "stripeToken": "tok_visa",
                "cardholderName": "Test Card",
            }
        )


def test_payment_method_request_accepts_full_billing_country():
    body = AddPaymentMethodRequest.model_validate(
        {
            "type": "card",
            "stripeToken": "tok_visa",
            "holderName": "Test Card",
            "billingCountry": "Canada",
            "billingPostalCode": "N6A 1A1",
        }
    )

    assert body.billing_country == "CA"
    assert body.billing_postal_code == "N6A 1A1"


def test_payment_method_request_accepts_plain_billing_country_alias():
    body = AddPaymentMethodRequest.model_validate(
        {
            "type": "card",
            "stripeToken": "tok_visa",
            "holderName": "Test Card",
            "billing": "Canada",
        }
    )

    assert body.billing_country == "CA"


def test_payment_method_request_accepts_stripe_payment_method_id():
    body = AddPaymentMethodRequest.model_validate(
        {
            "type": "card",
            "paymentMethodId": "pm_123",
            "holderName": "Test Card",
        }
    )

    assert body.stripe_payment_method_id == "pm_123"


def test_payment_method_request_rejects_missing_stripe_source():
    with pytest.raises(
        ValidationError,
        match="stripe_token or stripe_payment_method_id is required",
    ):
        AddPaymentMethodRequest.model_validate(
            {
                "type": "card",
                "holderName": "Test Card",
            }
        )


def test_payment_method_request_rejects_unknown_full_billing_country():
    with pytest.raises(
        ValidationError,
        match="Billing country must be a 2-letter ISO country code",
    ):
        AddPaymentMethodRequest.model_validate(
            {
                "type": "card",
                "stripeToken": "tok_visa",
                "holderName": "Test Card",
                "billingCountry": "Atlantis",
            }
        )
