import re
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    card_number: str = Field(..., min_length=13, max_length=19)
    expiry_month: str = Field(..., min_length=1, max_length=2, pattern=r"^(0?[1-9]|1[0-2])$")
    expiry_year: str = Field(..., min_length=2, max_length=4, pattern=r"^\d{2,4}$")
    holder_name: str = Field(..., min_length=1, max_length=200)
    cvd: str | None = Field(None, min_length=3, max_length=4)
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

        method_type = _first_present(data, "method_type", "methodType", "type")
        if method_type is not None:
            data["method_type"] = str(method_type)

        card_number = _first_present(data, "card_number", "cardNumber", "number")
        if card_number is not None:
            data["card_number"] = re.sub(r"\D", "", str(card_number))

        expiry_month = _first_present(
            data, "expiry_month", "expiryMonth", "exp_month", "expMonth"
        )
        expiry_year = _first_present(
            data, "expiry_year", "expiryYear", "exp_year", "expYear"
        )
        expiry_date = _first_present(
            data, "expiry_date", "expiryDate", "expiration_date", "expirationDate"
        )

        if expiry_date and (expiry_month is None or expiry_year is None):
            parts = re.findall(r"\d+", str(expiry_date))
            if len(parts) >= 2:
                expiry_month = expiry_month or parts[0]
                expiry_year = expiry_year or parts[1]

        if expiry_month is not None:
            data["expiry_month"] = str(expiry_month).zfill(2)
        if expiry_year is not None:
            data["expiry_year"] = str(expiry_year)

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

        cvd = _first_present(data, "cvd", "cvv", "cvc", "cvc2")
        if cvd is not None:
            data["cvd"] = str(cvd)

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

    @field_validator("expiry_year")
    @classmethod
    def normalize_expiry_year(cls, value: str) -> str:
        if len(value) == 4:
            return value
        return value.zfill(2)


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
