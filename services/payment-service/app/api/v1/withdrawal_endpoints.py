from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.moneris_client import MonerisClient
from app.config import settings
from app.dependencies import get_db, get_moneris_client, get_publisher
from app.repositories.earnings_repo import EarningsRepository
from app.repositories.payment_method_repo import PaymentMethodRepository
from app.repositories.withdrawal_repo import WithdrawalRepository
from app.schemas.withdrawal import WithdrawalFeeResponse, WithdrawalRequest, WithdrawalResponse
from app.services.withdrawal_service import WithdrawalService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import PaginatedResponse, StandardResponse

router = APIRouter()


def _get_withdrawal_service(
    session: AsyncSession = Depends(get_db),
    publisher: EventPublisher = Depends(get_publisher),
    moneris: MonerisClient = Depends(get_moneris_client),
) -> WithdrawalService:
    return WithdrawalService(
        withdrawal_repo=WithdrawalRepository(session),
        earnings_repo=EarningsRepository(session),
        payment_method_repo=PaymentMethodRepository(session),
        publisher=publisher,
        moneris_client=moneris,
    )


@router.post("/request", response_model=StandardResponse[WithdrawalResponse])
async def request_withdrawal(
    body: WithdrawalRequest,
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: WithdrawalService = Depends(_get_withdrawal_service),
):
    withdrawal = await service.request_withdrawal(user.id, body.amount, body.payment_method_id)
    return StandardResponse(
        data=WithdrawalResponse.model_validate(withdrawal),
        message="Withdrawal requested successfully",
    )


@router.get("/fee", response_model=StandardResponse[WithdrawalFeeResponse])
async def get_withdrawal_fee(
    amount: float = Query(..., gt=0),
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: WithdrawalService = Depends(_get_withdrawal_service),
):
    data = await service.get_withdrawal_fee(amount)
    return StandardResponse(data=WithdrawalFeeResponse(**data))


@router.get("/history", response_model=PaginatedResponse[WithdrawalResponse])
async def get_withdrawal_history(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: WithdrawalService = Depends(_get_withdrawal_service),
):
    offset = (page - 1) * limit
    withdrawals, total = await service.get_withdrawal_history(user.id, offset, limit)
    return PaginatedResponse(
        data=[WithdrawalResponse.model_validate(w) for w in withdrawals],
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )
