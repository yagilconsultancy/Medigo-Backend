import pytest
from pydantic import ValidationError

from app.schemas.payment_method import AddPaymentMethodRequest


def test_payment_method_request_accepts_existing_snake_case_payload():
    body = AddPaymentMethodRequest.model_validate(
        {
            "method_type": "credit_card",
            "card_number": "4242424242424242",
            "expiry_month": "04",
            "expiry_year": "28",
            "holder_name": "Test Card",
            "cvd": "123",
        }
    )

    assert body.method_type == "credit_card"
    assert body.card_number == "4242424242424242"
    assert body.expiry_month == "04"
    assert body.expiry_year == "28"
    assert body.cvd == "123"


def test_payment_method_request_accepts_mobile_camel_case_payload():
    body = AddPaymentMethodRequest.model_validate(
        {
            "type": "card",
            "cardNumber": "4242 4242 4242 4242",
            "expiryMonth": 4,
            "expiryYear": 2028,
            "cvv": "123",
            "holderName": "Test Card",
        }
    )

    assert body.method_type == "card"
    assert body.card_number == "4242424242424242"
    assert body.expiry_month == "04"
    assert body.expiry_year == "2028"
    assert body.cvd == "123"
    assert body.holder_name == "Test Card"


def test_payment_method_request_accepts_expiry_date_and_full_billing_country():
    body = AddPaymentMethodRequest.model_validate(
        {
            "type": "card",
            "cardNumber": "4242424242424242",
            "expiryDate": "04/28",
            "cvv": "123",
            "cardholderName": "Test Card",
            "billingCountry": "Canada",
            "billingPostalCode": "N6A 1A1",
        }
    )

    assert body.expiry_month == "04"
    assert body.expiry_year == "28"
    assert body.billing_country == "CA"
    assert body.billing_postal_code == "N6A 1A1"


def test_payment_method_request_accepts_plain_billing_country_alias():
    body = AddPaymentMethodRequest.model_validate(
        {
            "type": "card",
            "cardNumber": "4242424242424242",
            "expiryDate": "04/28",
            "cvv": "123",
            "holderName": "Test Card",
            "billing": "Canada",
        }
    )

    assert body.billing_country == "CA"


def test_payment_method_request_rejects_unknown_full_billing_country():
    with pytest.raises(
        ValidationError,
        match="Billing country must be a 2-letter ISO country code",
    ):
        AddPaymentMethodRequest.model_validate(
            {
                "type": "card",
                "cardNumber": "4242424242424242",
                "expiryDate": "04/28",
                "cvv": "123",
                "holderName": "Test Card",
                "billingCountry": "Atlantis",
            }
        )
