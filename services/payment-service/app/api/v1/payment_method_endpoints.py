from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.stripe_client import StripeClient
from app.dependencies import get_db, get_stripe_client
from app.repositories.payment_method_repo import PaymentMethodRepository
from app.schemas.payment_method import AddPaymentMethodRequest, PaymentMethodResponse
from app.services.payment_method_service import PaymentMethodService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_pm_service(
    session: AsyncSession = Depends(get_db),
    stripe: StripeClient = Depends(get_stripe_client),
) -> PaymentMethodService:
    return PaymentMethodService(
        pm_repo=PaymentMethodRepository(session),
        stripe_client=stripe,
    )


@router.get("/", response_model=StandardResponse[list[PaymentMethodResponse]])
async def list_payment_methods(
    user: UserClaims = Depends(require_role([UserRole.DRIVER, UserRole.RIDER])),
    service: PaymentMethodService = Depends(_get_pm_service),
):
    methods = await service.list_payment_methods(user.id)
    return StandardResponse(data=[PaymentMethodResponse.model_validate(m) for m in methods])


@router.post("/", response_model=StandardResponse[PaymentMethodResponse])
async def add_payment_method(
    body: AddPaymentMethodRequest,
    user: UserClaims = Depends(require_role([UserRole.DRIVER, UserRole.RIDER])),
    service: PaymentMethodService = Depends(_get_pm_service),
):
    method = await service.add_payment_method(
        user_id=user.id,
        method_type=body.method_type,
        holder_name=body.holder_name,
        stripe_token=body.stripe_token,
        stripe_payment_method_id=body.stripe_payment_method_id,
        billing_country=body.billing_country,
        billing_postal_code=body.billing_postal_code,
        billing_line1=body.billing_line1,
        billing_line2=body.billing_line2,
        billing_city=body.billing_city,
        billing_state=body.billing_state,
    )
    return StandardResponse(
        data=PaymentMethodResponse.model_validate(method),
        message="Payment method added",
    )


@router.put("/{pm_id}/default", response_model=StandardResponse[PaymentMethodResponse])
async def set_default_payment_method(
    pm_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.DRIVER, UserRole.RIDER])),
    service: PaymentMethodService = Depends(_get_pm_service),
):
    method = await service.set_default_method(user.id, pm_id)
    return StandardResponse(
        data=PaymentMethodResponse.model_validate(method),
        message="Default payment method updated",
    )


@router.delete("/{pm_id}", response_model=StandardResponse[None])
async def remove_payment_method(
    pm_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.DRIVER, UserRole.RIDER])),
    service: PaymentMethodService = Depends(_get_pm_service),
):
    await service.remove_payment_method(user.id, pm_id)
    return StandardResponse(message="Payment method removed")
