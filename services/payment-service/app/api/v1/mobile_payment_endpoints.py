from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.stripe_client import StripeClient
from app.dependencies import get_db, get_stripe_client
from app.repositories.payment_method_repo import PaymentMethodRepository
from app.repositories.transaction_repo import TransactionRepository
from app.schemas.mobile_payment import (
    CreateMobilePaymentIntentRequest,
    MobilePaymentIntentResponse,
)
from app.services.mobile_payment_service import MobilePaymentService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_mobile_payment_service(
    session: AsyncSession = Depends(get_db),
    stripe: StripeClient = Depends(get_stripe_client),
) -> MobilePaymentService:
    return MobilePaymentService(
        pm_repo=PaymentMethodRepository(session),
        tx_repo=TransactionRepository(session),
        stripe_client=stripe,
    )


@router.post("/payment-intent", response_model=StandardResponse[MobilePaymentIntentResponse])
async def create_mobile_payment_intent(
    body: CreateMobilePaymentIntentRequest,
    user: UserClaims = Depends(require_role([UserRole.DRIVER, UserRole.RIDER, UserRole.FACILITY])),
    service: MobilePaymentService = Depends(_get_mobile_payment_service),
):
    payment_intent = await service.create_payment_intent(
        user_id=user.id,
        email=user.email,
        amount=body.amount,
        currency=body.currency,
        description=body.description,
        order_id=body.order_id,
        metadata=body.metadata,
        customer_session_api_version=body.customer_session_api_version,
        setup_future_usage=body.setup_future_usage,
    )
    return StandardResponse(
        data=payment_intent,
        message="Mobile PaymentIntent created",
    )
