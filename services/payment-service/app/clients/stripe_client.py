import logging
from dataclasses import dataclass

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
    ):
        self._secret_key = secret_key
        self._publishable_key = publishable_key
        self._webhook_secret = webhook_secret
        stripe.api_key = secret_key

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
        card_number: str,
        expiry_month: str,
        expiry_year: str,
        holder_name: str,
        *,
        cvd: str | None = None,
        user_id: str,
        existing_customer_id: str | None = None,
    ) -> StripeVaultResult:
        """Create a Stripe PaymentMethod and attach it to a Customer.

        Returns data_key = pm_xxx (PaymentMethod ID) for compatibility.
        """
        try:
            exp_year = int(expiry_year) if len(expiry_year) == 4 else int(f"20{expiry_year}")

            pm = await stripe.PaymentMethod.create_async(
                type="card",
                card={
                    "number": card_number,
                    "exp_month": int(expiry_month),
                    "exp_year": exp_year,
                    "cvc": cvd,
                },
                billing_details={"name": holder_name},
            )

            customer_id = await self.get_or_create_customer(
                user_id=user_id,
                name=holder_name,
                existing_customer_id=existing_customer_id,
            )

            await stripe.PaymentMethod.attach_async(pm.id, customer=customer_id)

            return StripeVaultResult(
                success=True,
                data_key=pm.id,
                customer_id=customer_id,
                message="Card tokenized successfully",
            )
        except stripe_error.CardError as e:
            return StripeVaultResult(success=False, message=str(e.user_message))
        except stripe_error.StripeError as e:
            logger.error(f"Stripe tokenization failed: {e}")
            return StripeVaultResult(success=False, message=str(e))

    async def delete_vault_profile(self, data_key: str) -> bool:
        """Detach a PaymentMethod from its Customer."""
        try:
            await stripe.PaymentMethod.detach_async(data_key)
            return True
        except stripe_error.StripeError as e:
            logger.error(f"Stripe PaymentMethod detach failed: {e}")
            return False

    # ------------------------------------------------------------------ #
    # Payments
    # ------------------------------------------------------------------ #

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

        amount_cents = int(round(amount * 100))

        try:
            intent = await stripe.PaymentIntent.create_async(
                amount=amount_cents,
                currency="usd",
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

        try:
            intent = await stripe.PaymentIntent.create_async(
                amount=amount_cents,
                currency="usd",
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
                currency="usd",
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
    # Webhook Verification
    # ------------------------------------------------------------------ #

    def verify_webhook(self, payload: bytes, sig_header: str) -> dict:
        """Verify and parse a Stripe webhook event."""
        event = stripe.Webhook.construct_event(
            payload, sig_header, self._webhook_secret
        )
        return event
