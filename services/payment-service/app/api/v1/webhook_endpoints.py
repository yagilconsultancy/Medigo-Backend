import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.stripe_client import StripeClient
from app.dependencies import get_db, get_publisher, get_stripe_client
from app.repositories.transaction_repo import TransactionRepository
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher
from mediride_common.events.schemas import PaymentCompletedPayload
from mediride_common.schemas.enums import PaymentStatus

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db),
    stripe_client: StripeClient = Depends(get_stripe_client),
    publisher: EventPublisher = Depends(get_publisher),
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
):
    """Handle incoming Stripe webhook events."""
    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header",
        )

    payload = await request.body()

    try:
        event = stripe_client.verify_webhook(payload, stripe_signature)
    except Exception as e:
        logger.error(f"Stripe webhook verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature",
        )

    event_type = event["type"]
    logger.info(f"Stripe webhook received: {event_type}")
    tx_repo = TransactionRepository(session)
    stripe_object = event["data"]["object"]
    payment_intent_id = stripe_object["id"]

    # Look up transaction by payment_intent_id (stored as reference_id at creation)
    # This is the most reliable identifier — no metadata dependency
    tx = await tx_repo.get_by_reference_id(payment_intent_id)

    if event_type == "payment_intent.succeeded":
        if not tx:
            logger.warning(
                "No transaction found for PaymentIntent %s", payment_intent_id
            )
        elif tx.status != PaymentStatus.COMPLETED:
            update_kwargs: dict = {
                "status": PaymentStatus.COMPLETED,
                "reference_id": payment_intent_id,
            }
            try:
                amount_received = stripe_object["amount_received"]
                if amount_received is not None:
                    update_kwargs["amount"] = Decimal(str(amount_received)) / Decimal("100")
            except (KeyError, TypeError):
                pass
            try:
                currency = stripe_object["currency"]
                if currency:
                    update_kwargs["currency"] = str(currency).upper()
            except (KeyError, TypeError):
                pass
            await tx_repo.update(tx, **update_kwargs)
            logger.info("Transaction %s marked COMPLETED", tx.id)

            # Publish event so ride-service transitions ride from PENDING → REQUESTED
            if tx.ride_id:
                await publisher.publish(
                    Exchanges.PAYMENTS,
                    RoutingKeys.PAYMENT_COMPLETED,
                    PaymentCompletedPayload(
                        transaction_id=tx.id,
                        ride_id=tx.ride_id,
                        user_id=tx.user_id,
                        amount=float(tx.amount),
                        status=PaymentStatus.COMPLETED,
                    ).model_dump(mode="json"),
                )
                logger.info("Published PAYMENT_COMPLETED for ride %s", tx.ride_id)

    elif event_type == "payment_intent.payment_failed":
        if tx and tx.status != PaymentStatus.FAILED:
            await tx_repo.update(
                tx,
                status=PaymentStatus.FAILED,
                reference_id=payment_intent_id,
            )
            logger.info("Transaction %s marked FAILED", tx.id)

    elif event_type == "charge.refunded":
        pass
    elif event_type == "transfer.paid":
        pass
    else:
        logger.info(f"Unhandled Stripe event type: {event_type}")

    return {"status": "ok"}
