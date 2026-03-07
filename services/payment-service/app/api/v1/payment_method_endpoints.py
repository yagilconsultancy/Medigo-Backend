from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.moneris_client import MonerisClient
from app.dependencies import get_db, get_moneris_client
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
    moneris: MonerisClient = Depends(get_moneris_client),
) -> PaymentMethodService:
    return PaymentMethodService(
        pm_repo=PaymentMethodRepository(session),
        moneris_client=moneris,
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
        card_number=body.card_number,
        expiry_month=body.expiry_month,
        expiry_year=body.expiry_year,
        holder_name=body.holder_name,
        cvd=body.cvd,
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
