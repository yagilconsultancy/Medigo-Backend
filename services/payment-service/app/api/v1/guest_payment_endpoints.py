"""Guest payment intent endpoint – no JWT required.

The caller provides a ``session_id`` (from the guest-booking flow in
ride-service) instead of an auth token.  The endpoint resolves the guest
rider_id / email from that session and creates a Stripe PaymentIntent.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.ride_service_client import RideServiceClient
from app.clients.stripe_client import StripeClient
from app.config import settings
from app.dependencies import get_db, get_stripe_client
from app.repositories.payment_method_repo import PaymentMethodRepository
from app.repositories.transaction_repo import TransactionRepository
from app.schemas.mobile_payment import MobilePaymentIntentResponse
from app.services.mobile_payment_service import MobilePaymentService
from mediride_common.schemas.responses import StandardResponse

router = APIRouter(prefix="/guest")


# --------------- request schema ---------------

class CreateGuestPaymentIntentRequest(BaseModel):
    session_id: UUID = Field(..., description="Guest booking session ID from ride-service")
    amount: float = Field(..., gt=0)
    currency: str | None = Field(None)
    description: str | None = Field(None, max_length=500)
    order_id: str = Field(..., min_length=1, max_length=255)
    metadata: dict[str, str] = Field(default_factory=dict)


# --------------- helpers ---------------

def _get_ride_client() -> RideServiceClient:
    return RideServiceClient(settings.RIDE_SERVICE_URL)


def _get_mobile_payment_service(
    session: AsyncSession = Depends(get_db),
    stripe: StripeClient = Depends(get_stripe_client),
) -> MobilePaymentService:
    return MobilePaymentService(
        pm_repo=PaymentMethodRepository(session),
        tx_repo=TransactionRepository(session),
        stripe_client=stripe,
    )


# --------------- endpoint ---------------

@router.post("/payment-intent", response_model=StandardResponse[MobilePaymentIntentResponse])
async def create_guest_payment_intent(
    body: CreateGuestPaymentIntentRequest,
    ride_client: RideServiceClient = Depends(_get_ride_client),
    service: MobilePaymentService = Depends(_get_mobile_payment_service),
):
    """Create a Stripe PaymentIntent for a guest user.

    Instead of requiring a JWT, the guest identifies themselves via
    ``session_id`` which was returned when they created a guest session.
    """
    # 1. Resolve guest session from ride-service
    guest = await ride_client.get_guest_session(body.session_id)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest session not found")

    rider_id: UUID = UUID(str(guest["rider_id"]))
    email: str | None = guest.get("email")

    # 2. Create the payment intent via the shared service layer
    payment_intent = await service.create_payment_intent(
        user_id=rider_id,
        email=email,
        amount=body.amount,
        currency=body.currency,
        description=body.description,
        order_id=body.order_id,
        metadata={**body.metadata, "guest_session_id": str(body.session_id)},
    )

    return StandardResponse(
        data=payment_intent,
        message="Guest PaymentIntent created",
    )
