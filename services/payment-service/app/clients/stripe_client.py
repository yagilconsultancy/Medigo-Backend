import logging
from dataclasses import dataclass
from uuid import uuid4

import stripe
from stripe import error as stripe_error

from mediride_common.exceptions import ServiceUnavailableError, ValidationError

logger = logging.getLogger(__name__)


@dataclass
class StripePaymentResult:
    success: bool
    transaction_id: str | None = None
    reference_number: str | None = None
    response_code: str | None = None
    message: str | None = None
    raw_response: dict | None = None


@dataclass
class StripeVaultResult:
    success: bool
    data_key: str | None = None  # Stripe PaymentMethod ID (pm_xxx)
    customer_id: str | None = None  # Stripe Customer ID (cus_xxx)
    last_four: str | None = None
    brand: str | None = None
    message: str | None = None
    raw_response: dict | None = None


@dataclass
class StripeMobilePaymentIntentResult:
    success: bool
    payment_intent_id: str | None = None
    client_secret: str | None = None
    customer_id: str | None = None
    ephemeral_key_secret: str | None = None
    publishable_key: str | None = None
    amount: float | None = None
    currency: str | None = None
    message: str | None = None
    raw_response: dict | None = None


class StripeClient:
    """Async Stripe client for payment processing.

    Uses the official stripe Python library with native async support.
    """

    def __init__(
        self,
        secret_key: str,
        *,
        publishable_key: str = "",
        webhook_secret: str = "",
        environment: str = "development",
        mock_in_development: bool = True,
    ):
        self._secret_key = secret_key.strip()
        self._publishable_key = publishable_key
        self._webhook_secret = webhook_secret
        self._environment = environment.lower()
        self._mock_in_development = mock_in_development
        stripe.api_key = self._secret_key

    @property
    def publishable_key(self) -> str:
        return self._publishable_key

    @property
    def _mock_enabled(self) -> bool:
        return self._environment == "development" and self._mock_in_development

    def _mock_vault_result(
        self,
        user_id: str,
        *,
        existing_customer_id: str | None = None,
        reason: str,
    ) -> StripeVaultResult:
        customer_id = existing_customer_id or f"cus_mock_{user_id.replace('-', '')[:24]}"
        payment_method_id = f"pm_mock_{uuid4().hex}"
        logger.warning(
            "Using mock Stripe PaymentMethod in development: %s",
            reason,
        )
        return StripeVaultResult(
            success=True,
            data_key=payment_method_id,
            customer_id=customer_id,
            last_four="0000",
            brand="Mock",
            message="Card tokenized in development mock mode",
        )

    def _is_mock_payment_method(
        self,
        data_key: str | None,
        customer_id: str | None = None,
    ) -> bool:
        if not self._mock_enabled:
            return False
        if not data_key or not data_key.startswith("pm_mock_"):
            return False
        return customer_id is None or customer_id.startswith("cus_mock_")

    def _is_mock_transaction(self, transaction_id: str | None) -> bool:
        if not self._mock_enabled:
            return False
        return bool(transaction_id and transaction_id.startswith("pi_mock_"))

    @staticmethod
    def _card_attr(payment_method, attr: str) -> str | None:
        card = getattr(payment_method, "card", None)
        if not card:
            return None
        if isinstance(card, dict):
            return card.get(attr)
        return getattr(card, attr, None)

    @staticmethod
    def _display_brand(brand: str | None) -> str | None:
        if not brand:
            return None
        if brand.lower() == "amex":
            return "Amex"
        return brand.replace("_", " ").title()

    # ------------------------------------------------------------------ #
    # Customer Management
    # ------------------------------------------------------------------ #

    async def get_or_create_customer(
        self,
        user_id: str,
        *,
        email: str | None = None,
        name: str | None = None,
        existing_customer_id: str | None = None,
    ) -> str:
        """Return existing Stripe Customer ID or create a new one."""
        if existing_customer_id:
            return existing_customer_id
        if not self._secret_key and self._mock_enabled:
            return f"cus_mock_{user_id.replace('-', '')[:24]}"

        try:
            customer = await stripe.Customer.create_async(
                metadata={"mediride_user_id": user_id},
                email=email,
                name=name,
            )
            return customer.id
        except stripe_error.StripeError as e:
            logger.error(f"Stripe customer creation failed: {e}")
            raise ServiceUnavailableError("Failed to create Stripe customer")

    # ------------------------------------------------------------------ #
    # Vault (Tokenization)
    # ------------------------------------------------------------------ #

    async def tokenize_card(
        self,
        holder_name: str,
        *,
        stripe_token: str | None = None,
        stripe_payment_method_id: str | None = None,
        billing_country: str | None = None,
        billing_postal_code: str | None = None,
        billing_line1: str | None = None,
        billing_line2: str | None = None,
        billing_city: str | None = None,
        billing_state: str | None = None,
        user_id: str,
        existing_customer_id: str | None = None,
    ) -> StripeVaultResult:
        """Create a Stripe PaymentMethod and attach it to a Customer.

        Returns data_key = pm_xxx (PaymentMethod ID) for compatibility.
        """
        if not self._secret_key:
            if self._mock_enabled:
                return self._mock_vault_result(
                    user_id,
                    existing_customer_id=existing_customer_id,
                    reason="STRIPE_SECRET_KEY is not configured",
                )
            logger.error("Stripe tokenization failed: STRIPE_SECRET_KEY is not configured")
            return StripeVaultResult(
                success=False,
                message="Stripe is not configured",
            )

        try:
            billing_details = {"name": holder_name}
            address = {
                "country": billing_country,
                "postal_code": billing_postal_code,
                "line1": billing_line1,
                "line2": billing_line2,
                "city": billing_city,
                "state": billing_state,
            }
            address = {key: val for key, val in address.items() if val}
            if address:
                billing_details["address"] = address

            if stripe_payment_method_id:
                pm = await stripe.PaymentMethod.retrieve_async(stripe_payment_method_id)
                attached_customer_id = getattr(pm, "customer", None)
                customer_id = attached_customer_id or await self.get_or_create_customer(
                    user_id=user_id,
                    name=holder_name,
                    existing_customer_id=existing_customer_id,
                )
                if attached_customer_id != customer_id:
                    await stripe.PaymentMethod.attach_async(pm.id, customer=customer_id)
            else:
                if not stripe_token:
                    return StripeVaultResult(
                        success=False,
                        message="Missing Stripe token or PaymentMethod ID",
                    )

                customer_id = await self.get_or_create_customer(
                    user_id=user_id,
                    name=holder_name,
                    existing_customer_id=existing_customer_id,
                )
                pm = await stripe.PaymentMethod.create_async(
                    type="card",
                    card={"token": stripe_token},
                    billing_details=billing_details,
                )
                await stripe.PaymentMethod.attach_async(pm.id, customer=customer_id)

            return StripeVaultResult(
                success=True,
                data_key=pm.id,
                customer_id=customer_id,
                last_four=self._card_attr(pm, "last4"),
                brand=self._display_brand(self._card_attr(pm, "brand")),
                message="Card tokenized successfully",
            )
        except stripe_error.CardError as e:
            return StripeVaultResult(success=False, message=str(e.user_message))
        except stripe_error.StripeError as e:
            logger.error(f"Stripe tokenization failed: {e}")
            if self._mock_enabled:
                return self._mock_vault_result(
                    user_id,
                    existing_customer_id=existing_customer_id,
                    reason=str(e),
                )
            return StripeVaultResult(success=False, message=str(e))

    async def delete_vault_profile(self, data_key: str) -> bool:
        """Detach a PaymentMethod from its Customer."""
        if self._is_mock_payment_method(data_key):
            return True
        try:
            await stripe.PaymentMethod.detach_async(data_key)
            return True
        except stripe_error.StripeError as e:
            logger.error(f"Stripe PaymentMethod detach failed: {e}")
            return False

    # ------------------------------------------------------------------ #
    # Payments
    # ------------------------------------------------------------------ #

    async def create_mobile_payment_intent(
        self,
        user_id: str,
        amount: float,
        *,
        currency: str = "cad",
        email: str | None = None,
        description: str | None = None,
        metadata: dict[str, str] | None = None,
        existing_customer_id: str | None = None,
        customer_session_api_version: str | None = None,
        setup_future_usage: str | None = None,
    ) -> StripeMobilePaymentIntentResult:
        """Create a Stripe PaymentIntent for mobile SDK flows.

        Returns a real client secret and, when requested, a customer-scoped
        ephemeral key for Stripe's mobile SDKs.
        """
        if amount <= 0:
            raise ValidationError("Amount must be greater than zero")
        if not self._secret_key:
            return StripeMobilePaymentIntentResult(
                success=False,
                message="Stripe mobile SDK setup requires STRIPE_SECRET_KEY",
            )
        if not self._publishable_key:
            return StripeMobilePaymentIntentResult(
                success=False,
                message="Stripe mobile SDK setup requires STRIPE_PUBLISHABLE_KEY",
            )

        amount_cents = int(round(amount * 100))
        normalized_currency = currency.lower()

        try:
            customer_id = await self.get_or_create_customer(
                user_id=user_id,
                email=email,
                existing_customer_id=existing_customer_id,
            )

            intent = await stripe.PaymentIntent.create_async(
                amount=amount_cents,
                currency=normalized_currency,
                customer=customer_id,
                automatic_payment_methods={"enabled": True},
                description=description,
                metadata=metadata or {},
                setup_future_usage=setup_future_usage,
            )

            ephemeral_key_secret = None
            if customer_session_api_version:
                ephemeral_key = await stripe.EphemeralKey.create_async(
                    customer=customer_id,
                    stripe_version=customer_session_api_version,
                )
                ephemeral_key_secret = getattr(ephemeral_key, "secret", None)

            return StripeMobilePaymentIntentResult(
                success=True,
                payment_intent_id=intent.id,
                client_secret=getattr(intent, "client_secret", None),
                customer_id=customer_id,
                ephemeral_key_secret=ephemeral_key_secret,
                publishable_key=self._publishable_key,
                amount=amount,
                currency=normalized_currency.upper(),
                message="PaymentIntent created",
            )
        except stripe_error.StripeError as e:
            logger.error(f"Stripe mobile PaymentIntent error: {e}")
            return StripeMobilePaymentIntentResult(success=False, message=str(e))

    async def purchase(
        self,
        order_id: str,
        amount: float,
        *,
        data_key: str | None = None,
        customer_id: str | None = None,
        description: str | None = None,
    ) -> StripePaymentResult:
        """Process a purchase using an attached PaymentMethod."""
        if not data_key or not customer_id:
            raise ValidationError(
                "PaymentMethod ID (data_key) and customer_id required for Stripe purchase"
            )
        if self._is_mock_payment_method(data_key, customer_id):
            return StripePaymentResult(
                success=True,
                transaction_id=f"pi_mock_{uuid4().hex}",
                reference_number=f"ch_mock_{uuid4().hex}",
                response_code="succeeded",
                message="Payment succeeded in development mock mode",
            )

        amount_cents = int(round(amount * 100))

        try:
            intent = await stripe.PaymentIntent.create_async(
                amount=amount_cents,
                currency="cad",
                customer=customer_id,
                payment_method=data_key,
                off_session=True,
                confirm=True,
                description=description,
                metadata={"order_id": order_id},
            )

            success = intent.status == "succeeded"
            return StripePaymentResult(
                success=success,
                transaction_id=intent.id,
                reference_number=intent.latest_charge if hasattr(intent, "latest_charge") else None,
                response_code=intent.status,
                message="Payment succeeded" if success else f"Payment status: {intent.status}",
            )
        except stripe_error.CardError as e:
            return StripePaymentResult(
                success=False,
                response_code="card_error",
                message=str(e.user_message),
            )
        except stripe_error.StripeError as e:
            logger.error(f"Stripe purchase error: {e}")
            return StripePaymentResult(success=False, message=str(e))

    async def preauth(
        self,
        order_id: str,
        amount: float,
        *,
        data_key: str,
        customer_id: str,
    ) -> StripePaymentResult:
        """Pre-authorize an amount (capture_method=manual)."""
        amount_cents = int(round(amount * 100))
        if self._is_mock_payment_method(data_key, customer_id):
            return StripePaymentResult(
                success=True,
                transaction_id=f"pi_mock_{uuid4().hex}",
                response_code="requires_capture",
                message="Pre-authorization succeeded in development mock mode",
            )

        try:
            intent = await stripe.PaymentIntent.create_async(
                amount=amount_cents,
                currency="cad",
                customer=customer_id,
                payment_method=data_key,
                capture_method="manual",
                off_session=True,
                confirm=True,
                metadata={"order_id": order_id},
            )

            success = intent.status == "requires_capture"
            return StripePaymentResult(
                success=success,
                transaction_id=intent.id,
                response_code=intent.status,
                message="Pre-authorization succeeded" if success else f"Status: {intent.status}",
            )
        except stripe_error.StripeError as e:
            logger.error(f"Stripe preauth error: {e}")
            return StripePaymentResult(success=False, message=str(e))

    async def capture(
        self,
        order_id: str,
        transaction_id: str,
        amount: float,
    ) -> StripePaymentResult:
        """Capture a previously pre-authorized PaymentIntent."""
        if self._is_mock_transaction(transaction_id):
            return StripePaymentResult(
                success=True,
                transaction_id=transaction_id,
                response_code="succeeded",
                message="Capture succeeded in development mock mode",
            )

        amount_cents = int(round(amount * 100))

        try:
            intent = await stripe.PaymentIntent.capture_async(
                transaction_id,
                amount_to_capture=amount_cents,
            )

            success = intent.status == "succeeded"
            return StripePaymentResult(
                success=success,
                transaction_id=intent.id,
                response_code=intent.status,
                message="Capture succeeded" if success else f"Status: {intent.status}",
            )
        except stripe_error.StripeError as e:
            logger.error(f"Stripe capture error: {e}")
            return StripePaymentResult(success=False, message=str(e))

    async def refund(
        self,
        order_id: str,
        transaction_id: str,
        amount: float,
    ) -> StripePaymentResult:
        """Refund a completed PaymentIntent."""
        if self._is_mock_transaction(transaction_id):
            return StripePaymentResult(
                success=True,
                transaction_id=f"re_mock_{uuid4().hex}",
                response_code="succeeded",
                message="Refund succeeded in development mock mode",
            )

        amount_cents = int(round(amount * 100))

        try:
            refund_obj = await stripe.Refund.create_async(
                payment_intent=transaction_id,
                amount=amount_cents,
                metadata={"order_id": order_id},
            )

            success = refund_obj.status == "succeeded"
            return StripePaymentResult(
                success=success,
                transaction_id=refund_obj.id,
                reference_number=refund_obj.charge if hasattr(refund_obj, "charge") else None,
                response_code=refund_obj.status,
                message="Refund succeeded" if success else f"Refund status: {refund_obj.status}",
            )
        except stripe_error.StripeError as e:
            logger.error(f"Stripe refund error: {e}")
            return StripePaymentResult(success=False, message=str(e))

    async def void(
        self,
        order_id: str,
        transaction_id: str,
    ) -> StripePaymentResult:
        """Cancel an uncaptured PaymentIntent."""
        if self._is_mock_transaction(transaction_id):
            return StripePaymentResult(
                success=True,
                transaction_id=transaction_id,
                response_code="canceled",
                message="PaymentIntent cancelled in development mock mode",
            )

        try:
            intent = await stripe.PaymentIntent.cancel_async(transaction_id)
            return StripePaymentResult(
                success=True,
                transaction_id=intent.id,
                response_code=intent.status,
                message="PaymentIntent cancelled",
            )
        except stripe_error.StripeError as e:
            logger.error(f"Stripe void error: {e}")
            return StripePaymentResult(success=False, message=str(e))

    # ------------------------------------------------------------------ #
    # Payout / Fund Transfer (for driver withdrawals)
    # ------------------------------------------------------------------ #

    async def process_payout(
        self,
        order_id: str,
        amount: float,
        data_key: str,
        *,
        connected_account_id: str | None = None,
    ) -> StripePaymentResult:
        """Process a payout to a driver via Stripe Transfer.

        Requires a Stripe Connected Account (acct_xxx) for the driver.
        """
        amount_cents = int(round(amount * 100))

        if not connected_account_id:
            return StripePaymentResult(
                success=False,
                message="Driver does not have a Stripe Connected Account configured",
            )

        try:
            transfer = await stripe.Transfer.create_async(
                amount=amount_cents,
                currency="cad",
                destination=connected_account_id,
                metadata={"order_id": order_id},
            )

            return StripePaymentResult(
                success=True,
                transaction_id=transfer.id,
                response_code="succeeded",
                message="Payout transfer succeeded",
            )
        except stripe_error.StripeError as e:
            logger.error(f"Stripe payout error: {e}")
            return StripePaymentResult(success=False, message=str(e))

    # ------------------------------------------------------------------ #
    # Retrieve PaymentIntent
    # ------------------------------------------------------------------ #

    async def retrieve_payment_intent(self, payment_intent_id: str) -> dict | None:
        """Retrieve a PaymentIntent from Stripe by ID."""
        try:
            intent = await stripe.PaymentIntent.retrieve_async(payment_intent_id)
            return intent
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    # Webhook Verification
    # ------------------------------------------------------------------ #

    def verify_webhook(self, payload: bytes, sig_header: str) -> dict:
        """Verify and parse a Stripe webhook event."""
        event = stripe.Webhook.construct_event(
            payload, sig_header, self._webhook_secret
        )
        return event
