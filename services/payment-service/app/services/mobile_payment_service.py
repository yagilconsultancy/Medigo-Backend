from uuid import UUID

from app.clients.stripe_client import StripeClient
from app.config import settings
from app.repositories.payment_method_repo import PaymentMethodRepository
from app.repositories.transaction_repo import TransactionRepository
from app.schemas.mobile_payment import MobilePaymentIntentResponse
from app.models.transaction import Transaction
from mediride_common.exceptions import ServiceUnavailableError
from mediride_common.schemas.enums import PaymentStatus, TransactionType


class MobilePaymentService:
    def __init__(
        self,
        pm_repo: PaymentMethodRepository,
        tx_repo: TransactionRepository,
        stripe_client: StripeClient,
    ):
        self.pm_repo = pm_repo
        self.tx_repo = tx_repo
        self.stripe = stripe_client

    async def create_payment_intent(
        self,
        *,
        user_id: UUID,
        email: str | None,
        amount: float,
        currency: str | None = None,
        description: str | None = None,
        order_id: str,
        metadata: dict[str, str] | None = None,
        customer_session_api_version: str | None = None,
        setup_future_usage: str | None = None,
    ) -> MobilePaymentIntentResponse:
        methods = await self.pm_repo.get_by_user(user_id)
        existing_customer_id = next(
            (method.stripe_customer_id for method in methods if method.stripe_customer_id),
            None,
        )

        resolved_metadata = dict(metadata or {})
        resolved_metadata.setdefault("mediride_user_id", str(user_id))
        resolved_metadata.setdefault("order_id", order_id)

        result = await self.stripe.create_mobile_payment_intent(
            user_id=str(user_id),
            amount=amount,
            currency=currency or settings.DEFAULT_CURRENCY,
            email=email,
            description=description,
            metadata=resolved_metadata,
            existing_customer_id=existing_customer_id,
            customer_session_api_version=customer_session_api_version,
            setup_future_usage=setup_future_usage,
        )

        if not result.success or not result.client_secret or not result.customer_id:
            raise ServiceUnavailableError(
                f"Unable to create mobile PaymentIntent: {result.message or 'Unknown Stripe error'}"
            )

        existing_tx = await self.tx_repo.get_by_order_id(order_id)
        if existing_tx:
            await self.tx_repo.update(
                existing_tx,
                amount=amount,
                currency=(result.currency or (currency or settings.DEFAULT_CURRENCY).upper()),
                status=PaymentStatus.PENDING,
                reference_id=result.payment_intent_id,
                description=f"Mobile PaymentIntent order_id={order_id}",
            )
        else:
            await self.tx_repo.create(
                Transaction(
                    user_id=user_id,
                    transaction_type=TransactionType.RIDE_PAYMENT,
                    amount=amount,
                    currency=(result.currency or (currency or settings.DEFAULT_CURRENCY).upper()),
                    status=PaymentStatus.PENDING,
                    reference_id=result.payment_intent_id,
                    description=f"Mobile PaymentIntent order_id={order_id}",
                )
            )

        return MobilePaymentIntentResponse(
            payment_intent=result.client_secret,
            payment_intent_id=result.payment_intent_id or "",
            customer=result.customer_id,
            ephemeral_key=result.ephemeral_key_secret,
            publishable_key=result.publishable_key or self.stripe.publishable_key,
            amount=result.amount or amount,
            currency=result.currency or (currency or settings.DEFAULT_CURRENCY).upper(),
        )
