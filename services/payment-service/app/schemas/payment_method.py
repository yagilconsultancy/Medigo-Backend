import re
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


_COUNTRY_NAME_TO_CODE = {
    "canada": "CA",
    "ca": "CA",
    "united states": "US",
    "united states of america": "US",
    "usa": "US",
    "u.s.a.": "US",
    "us": "US",
    "u.s.": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "great britain": "GB",
    "gb": "GB",
}
_RAW_CARD_FIELD_ALIASES = {
    "card_number",
    "cardNumber",
    "number",
    "expiry_month",
    "expiryMonth",
    "exp_month",
    "expMonth",
    "expiry_year",
    "expiryYear",
    "exp_year",
    "expYear",
    "expiry_date",
    "expiryDate",
    "expiration_date",
    "expirationDate",
    "cvd",
    "cvv",
    "cvc",
    "cvc2",
}


def _first_present(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _normalize_country(value: Any) -> str | None:
    if value in (None, ""):
        return None

    normalized = str(value).strip()
    if not normalized:
        return None

    mapped = _COUNTRY_NAME_TO_CODE.get(normalized.casefold())
    if mapped:
        return mapped

    compact = normalized.upper()
    if re.fullmatch(r"[A-Z]{2}", compact):
        return compact

    raise ValueError("Billing country must be a 2-letter ISO country code")


class AddPaymentMethodRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    method_type: str = Field(..., description="e.g. 'credit_card', 'debit_card'")
    holder_name: str = Field(..., min_length=1, max_length=200)
    stripe_token: str | None = Field(None, max_length=255)
    stripe_payment_method_id: str | None = Field(None, max_length=255)
    billing_country: str | None = Field(None, min_length=2, max_length=2)
    billing_postal_code: str | None = Field(None, max_length=20)
    billing_line1: str | None = Field(None, max_length=200)
    billing_line2: str | None = Field(None, max_length=200)
    billing_city: str | None = Field(None, max_length=100)
    billing_state: str | None = Field(None, max_length=100)

    @model_validator(mode="before")
    @classmethod
    def normalize_client_payload(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        data = dict(value)
        raw_keys = sorted(key for key in data if key in _RAW_CARD_FIELD_ALIASES)
        if raw_keys:
            raise ValueError(
                "Raw card fields are not accepted. Tokenize the card with the "
                "Stripe SDK and send stripeToken or paymentMethodId."
            )

        method_type = _first_present(data, "method_type", "methodType", "type")
        if method_type is not None:
            data["method_type"] = str(method_type)

        holder_name = _first_present(
            data,
            "holder_name",
            "holderName",
            "cardholder_name",
            "cardholderName",
            "card_holder_name",
            "cardHolderName",
            "name",
        )
        if holder_name is not None:
            data["holder_name"] = str(holder_name).strip()

        stripe_token = _first_present(data, "stripe_token", "stripeToken", "token")
        if stripe_token is not None:
            data["stripe_token"] = str(stripe_token).strip()

        stripe_payment_method_id = _first_present(
            data,
            "stripe_payment_method_id",
            "stripePaymentMethodId",
            "payment_method_id",
            "paymentMethodId",
        )
        if stripe_payment_method_id is not None:
            data["stripe_payment_method_id"] = str(stripe_payment_method_id).strip()

        billing_country = _first_present(
            data,
            "billing_country",
            "billingCountry",
            "country",
        )
        billing = data.get("billing")
        if isinstance(billing, dict):
            billing_address = billing
            billing_country = billing_country or _first_present(billing_address, "country")
            data["billing_postal_code"] = data.get("billing_postal_code") or _first_present(
                billing_address, "postal_code", "postalCode", "zip", "zipCode"
            )
            data["billing_line1"] = data.get("billing_line1") or _first_present(
                billing_address, "line1", "address_line1", "addressLine1"
            )
            data["billing_line2"] = data.get("billing_line2") or _first_present(
                billing_address, "line2", "address_line2", "addressLine2"
            )
            data["billing_city"] = data.get("billing_city") or _first_present(billing_address, "city")
            data["billing_state"] = data.get("billing_state") or _first_present(
                billing_address, "state", "province", "region"
            )
        elif billing not in (None, ""):
            billing_country = billing_country or billing
        if isinstance(data.get("billing_address"), dict):
            billing_address = data["billing_address"]
            billing_country = billing_country or _first_present(billing_address, "country")
            data["billing_postal_code"] = data.get("billing_postal_code") or _first_present(
                billing_address, "postal_code", "postalCode", "zip", "zipCode"
            )
            data["billing_line1"] = data.get("billing_line1") or _first_present(
                billing_address, "line1", "address_line1", "addressLine1"
            )
            data["billing_line2"] = data.get("billing_line2") or _first_present(
                billing_address, "line2", "address_line2", "addressLine2"
            )
            data["billing_city"] = data.get("billing_city") or _first_present(billing_address, "city")
            data["billing_state"] = data.get("billing_state") or _first_present(
                billing_address, "state", "province", "region"
            )

        if billing_country is not None:
            data["billing_country"] = _normalize_country(billing_country)

        data["billing_postal_code"] = data.get("billing_postal_code") or _first_present(
            data, "billingPostalCode", "postal_code", "postalCode", "zip", "zipCode"
        )
        data["billing_line1"] = data.get("billing_line1") or _first_present(
            data, "billingLine1", "address_line1", "addressLine1", "line1"
        )
        data["billing_line2"] = data.get("billing_line2") or _first_present(
            data, "billingLine2", "address_line2", "addressLine2", "line2"
        )
        data["billing_city"] = data.get("billing_city") or _first_present(data, "billingCity", "city")
        data["billing_state"] = data.get("billing_state") or _first_present(
            data, "billingState", "state", "province", "region"
        )

        return data

    @model_validator(mode="after")
    def require_stripe_source(self) -> "AddPaymentMethodRequest":
        if not self.stripe_token and not self.stripe_payment_method_id:
            raise ValueError("stripe_token or stripe_payment_method_id is required")
        return self


class PaymentMethodResponse(BaseModel):
    id: UUID
    user_id: UUID
    method_type: str
    last_four: str
    brand: str | None = None
    holder_name: str
    is_default: bool
    created_at: datetime

    model_config = {"from_attributes": True}
