import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.clients.stripe_client import StripeClient
from app.dependencies import get_stripe_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
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

    if event_type == "payment_intent.succeeded":
        pass
    elif event_type == "payment_intent.payment_failed":
        pass
    elif event_type == "charge.refunded":
        pass
    elif event_type == "transfer.paid":
        pass
    else:
        logger.info(f"Unhandled Stripe event type: {event_type}")

    return {"status": "ok"}
