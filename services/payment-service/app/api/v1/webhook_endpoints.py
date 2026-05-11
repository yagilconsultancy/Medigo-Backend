import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.stripe_client import StripeClient
from app.dependencies import get_db, get_stripe_client
from app.repositories.transaction_repo import TransactionRepository
from mediride_common.schemas.enums import PaymentStatus

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db),
    stripe_client: StripeClient = Depends(get_stripe_client),
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

    event_type = event.get("type", "")
    logger.info(f"Stripe webhook received: {event_type}")
    tx_repo = TransactionRepository(session)
    stripe_object = (event.get("data") or {}).get("object") or {}
    metadata = stripe_object.get("metadata") or {}
    order_id = metadata.get("order_id")
    payment_intent_id = stripe_object.get("id")

    if event_type == "payment_intent.succeeded":
        if not order_id:
            logger.warning("Stripe payment_intent.succeeded missing order_id metadata")
        else:
            tx = await tx_repo.get_by_order_id(order_id)
            if not tx and payment_intent_id:
                tx = await tx_repo.get_by_reference_id(payment_intent_id)

            if not tx:
                logger.warning("No transaction found for Stripe order_id=%s", order_id)
            elif tx.status != PaymentStatus.COMPLETED:
                amount_received = stripe_object.get("amount_received")
                currency = stripe_object.get("currency")
                update_kwargs = {
                    "status": PaymentStatus.COMPLETED,
                    "reference_id": payment_intent_id or tx.reference_id,
                    "description": f"Mobile PaymentIntent order_id={order_id}",
                }
                if amount_received is not None:
                    update_kwargs["amount"] = Decimal(str(amount_received)) / Decimal("100")
                if currency:
                    update_kwargs["currency"] = str(currency).upper()
                await tx_repo.update(tx, **update_kwargs)
    elif event_type == "payment_intent.payment_failed":
        if not order_id:
            logger.warning("Stripe payment_intent.payment_failed missing order_id metadata")
        else:
            tx = await tx_repo.get_by_order_id(order_id)
            if not tx and payment_intent_id:
                tx = await tx_repo.get_by_reference_id(payment_intent_id)
            if tx and tx.status != PaymentStatus.FAILED:
                await tx_repo.update(
                    tx,
                    status=PaymentStatus.FAILED,
                    reference_id=payment_intent_id or tx.reference_id,
                    description=f"Mobile PaymentIntent order_id={order_id}",
                )
    elif event_type == "charge.refunded":
        pass
    elif event_type == "transfer.paid":
        pass
    else:
        logger.info(f"Unhandled Stripe event type: {event_type}")

    return {"status": "ok"}
