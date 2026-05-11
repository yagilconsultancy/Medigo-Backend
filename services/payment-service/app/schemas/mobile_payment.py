import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.payment_method import _first_present


class CreateMobilePaymentIntentRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    amount: float = Field(..., gt=0)
    currency: str | None = Field(None)
    description: str | None = Field(None, max_length=500)
    order_id: str = Field(..., min_length=1, max_length=255)
    metadata: dict[str, str] = Field(default_factory=dict)
    customer_session_api_version: str | None = Field(None, max_length=64)
    setup_future_usage: Literal["on_session", "off_session"] | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_client_payload(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        data = dict(value)

        amount = _first_present(data, "amount", "amountMajor", "amount_major")
        if amount is not None:
            data["amount"] = amount

        currency = _first_present(data, "currency", "currencyCode", "currency_code")
        if currency is not None:
            data["currency"] = str(currency).strip().upper()

        description = _first_present(data, "description", "paymentDescription", "payment_description")
        if description is not None:
            data["description"] = str(description).strip()

        order_id = _first_present(data, "order_id", "orderId", "reference", "referenceId")
        if order_id is not None:
            data["order_id"] = str(order_id).strip()

        api_version = _first_present(
            data,
            "customer_session_api_version",
            "customerSessionApiVersion",
            "stripe_version",
            "stripeVersion",
        )
        if api_version is not None:
            data["customer_session_api_version"] = str(api_version).strip()

        setup_future_usage = _first_present(data, "setup_future_usage", "setupFutureUsage")
        if setup_future_usage is not None:
            data["setup_future_usage"] = str(setup_future_usage).strip()

        metadata = data.get("metadata")
        if isinstance(metadata, dict):
            data["metadata"] = {
                str(key): "" if raw_value is None else str(raw_value)
                for key, raw_value in metadata.items()
            }

        return data

    @model_validator(mode="after")
    def validate_currency(self) -> "CreateMobilePaymentIntentRequest":
        if self.currency and not re.fullmatch(r"[A-Z]{3}", self.currency):
            raise ValueError("Currency must be a 3-letter ISO code")
        return self


class MobilePaymentIntentResponse(BaseModel):
    payment_intent: str
    payment_intent_id: str
    customer: str
    ephemeral_key: str | None = None
    publishable_key: str
    amount: float
    currency: str
