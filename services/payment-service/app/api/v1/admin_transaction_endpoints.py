from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.ride_service_client import RideServiceClient
from app.clients.user_service_client import UserServiceClient
from app.config import settings
from app.dependencies import get_db
from app.repositories.admin_transaction_repo import AdminTransactionRepository
from app.repositories.fare_repo import FareBreakdownRepository
from app.schemas.admin_transaction import (
    AdminTransactionDetailResponse,
    AdminTransactionResponse,
    PaymentMethodBreakdownItem,
    TransactionKPIsResponse,
)
from app.services.admin_transaction_service import AdminTransactionService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import PaginatedResponse, StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> AdminTransactionService:
    return AdminTransactionService(
        tx_repo=AdminTransactionRepository(session),
        fare_repo=FareBreakdownRepository(session),
        user_client=UserServiceClient(settings.USER_SERVICE_URL),
        ride_client=RideServiceClient(settings.RIDE_SERVICE_URL),
    )


@router.get(
    "/transactions/kpis",
    response_model=StandardResponse[TransactionKPIsResponse],
)
async def get_transaction_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminTransactionService = Depends(_get_service),
):
    """Get transaction KPI cards."""
    data = await service.get_transaction_kpis()
    return StandardResponse(data=TransactionKPIsResponse(**data))


@router.get(
    "/transactions/payment-method-breakdown",
    response_model=StandardResponse[list[PaymentMethodBreakdownItem]],
)
async def get_payment_method_breakdown(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminTransactionService = Depends(_get_service),
):
    """Get payment method breakdown with totals."""
    data = await service.get_payment_method_breakdown()
    return StandardResponse(data=[PaymentMethodBreakdownItem(**item) for item in data])


@router.get(
    "/transactions",
    response_model=PaginatedResponse[AdminTransactionResponse],
)
async def get_all_transactions(
    status: str | None = Query(default=None, description="all|completed|pending|failed"),
    search: str | None = Query(default=None, description="Search by transaction ID or name"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminTransactionService = Depends(_get_service),
):
    """List all transactions with status filtering and search."""
    status_filter = status if status and status != "all" else None
    items, total = await service.get_all_transactions(status_filter, search, page, limit)
    return PaginatedResponse(
        data=[AdminTransactionResponse(**item) for item in items],
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.get(
    "/transactions/{transaction_id}",
    response_model=StandardResponse[AdminTransactionDetailResponse],
)
async def get_transaction_detail(
    transaction_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminTransactionService = Depends(_get_service),
):
    """Get transaction detail for modal view."""
    data = await service.get_transaction_detail(transaction_id)
    if not data:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return StandardResponse(data=AdminTransactionDetailResponse(**data))
