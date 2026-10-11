import hashlib
import json
import logging
from uuid import UUID

from app.clients.ride_service_client import RideServiceClient
from app.clients.stripe_client import StripeClient
from app.config import settings
from app.repositories.payment_method_repo import PaymentMethodRepository
from app.repositories.transaction_repo import TransactionRepository
from app.schemas.mobile_payment import MobilePaymentIntentResponse
from app.models.transaction import Transaction
from mediride_common.exceptions import (
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
)
from mediride_common.schemas.enums import PaymentStatus, TransactionType

logger = logging.getLogger(__name__)

# Rides that can no longer be paid for.
_UNPAYABLE_RIDE_STATUSES = {"cancelled", "no_show"}
# Largest difference (in dollars) between what the app sent and the ride's
# stored fare before we log it as suspicious.
_AMOUNT_TOLERANCE = 0.01


def _require_uuid(value: str, field: str) -> UUID:
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        raise ValidationError(f"Invalid {field}: '{value}' is not a valid UUID")


class MobilePaymentService:
    def __init__(
        self,
        pm_repo: PaymentMethodRepository,
        tx_repo: TransactionRepository,
        stripe_client: StripeClient,
        ride_client: RideServiceClient,
    ):
        self.pm_repo = pm_repo
        self.tx_repo = tx_repo
        self.stripe = stripe_client
        self.ride_client = ride_client

    @staticmethod
    def _is_party_to_ride(ride: dict, user_id: UUID) -> bool:
        """Same rule as ride-service ``can_access_ride`` for riders and facilities.

        Only the person who booked the ride, or the caregiver attached to it,
        may pay for it. Drivers and everyone else may not.
        """
        allowed = {ride.get("rider_id"), ride.get("caregiver_id")}
        allowed.discard(None)
        return str(user_id) in {str(a) for a in allowed}

    async def _resolve_amount(
        self, *, ride: dict, ride_uuid: UUID, user_id: UUID, requested: float
    ) -> float:
        """Work out what the rider owes, from the ride and not from the request."""
        status = str(ride.get("status") or "").lower()
        if status in _UNPAYABLE_RIDE_STATUSES:
            raise ConflictError("This ride was cancelled and cannot be paid for")

        # A rider who already paid must never be charged a second time.
        for tx in await self.tx_repo.get_by_ride_id(ride_uuid):
            if (
                tx.transaction_type == TransactionType.RIDE_PAYMENT
                and tx.status == PaymentStatus.COMPLETED
                and tx.user_id == user_id
            ):
                raise ConflictError("This ride has already been paid for")

        stored = ride.get("final_fare") if status == "completed" else ride.get("estimated_fare")
        if stored is None:
            stored = ride.get("estimated_fare")
        if stored is None or float(stored) <= 0:
            # No fare on record to check against. Keep the old behaviour but say so.
            logger.warning(
                "Ride %s has no stored fare; using the amount sent by the client", ride_uuid
            )
            return requested

        server_amount = round(float(stored), 2)
        if abs(server_amount - requested) > _AMOUNT_TOLERANCE:
            logger.warning(
                "Payment amount mismatch on ride %s: client sent %.2f, ride fare is %.2f. "
                "Using the ride fare.",
                ride_uuid,
                requested,
                server_amount,
            )
        return server_amount

    @staticmethod
    def _idempotency_key(
        *, user_id: UUID, ride_uuid: UUID, amount: float, currency: str,
        description: str | None, metadata: dict[str, str], setup_future_usage: str | None,
    ) -> str:
        """Same request twice (double tap, retry) gives Stripe the same key, so
        only one PaymentIntent is created."""
        fingerprint = json.dumps(
            [str(user_id), str(ride_uuid), int(round(amount * 100)), currency.lower(),
             description or "", sorted(metadata.items()), setup_future_usage or ""],
            sort_keys=True,
        )
        return "mobile-pi-" + hashlib.sha256(fingerprint.encode()).hexdigest()

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
        ride_uuid = _require_uuid(order_id, "order_id")

        ride = await self.ride_client.get_ride(ride_uuid)
        if ride is None:
            # get_ride returns None for both "not found" and "service unreachable".
            raise NotFoundError("Ride not found")
        if not self._is_party_to_ride(ride, user_id):
            # 404, not 403, so ride ids cannot be probed.
            raise NotFoundError("Ride not found")

        amount = await self._resolve_amount(
            ride=ride, ride_uuid=ride_uuid, user_id=user_id, requested=amount
        )

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
            idempotency_key=self._idempotency_key(
                user_id=user_id,
                ride_uuid=ride_uuid,
                amount=amount,
                currency=currency or settings.DEFAULT_CURRENCY,
                description=description,
                metadata=resolved_metadata,
                setup_future_usage=setup_future_usage,
            ),
        )

        if not result.success or not result.client_secret or not result.customer_id:
            raise ServiceUnavailableError(
                f"Unable to create mobile PaymentIntent: {result.message or 'Unknown Stripe error'}"
            )

        existing_tx = await self.tx_repo.get_by_order_id(order_id)
        if existing_tx and existing_tx.status != PaymentStatus.COMPLETED:
            await self.tx_repo.update(
                existing_tx,
                ride_id=ride_uuid,
                amount=amount,
                currency=(result.currency or (currency or settings.DEFAULT_CURRENCY).upper()),
                status=PaymentStatus.PENDING,
                reference_id=result.payment_intent_id,
                description=f"Mobile PaymentIntent order_id={order_id}",
            )
        else:
            await self.tx_repo.create(
                Transaction(
                    ride_id=ride_uuid,
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
