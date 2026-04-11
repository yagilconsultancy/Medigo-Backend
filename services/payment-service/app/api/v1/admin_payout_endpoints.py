from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.stripe_client import StripeClient
from app.clients.user_service_client import UserServiceClient
from app.config import settings
from app.dependencies import get_db, get_publisher, get_stripe_client
from app.repositories.admin_payout_repo import AdminPayoutRepository
from app.repositories.caregiver_commission_repo import CaregiverCommissionRepository
from app.repositories.earnings_repo import EarningsRepository
from app.repositories.payment_method_repo import PaymentMethodRepository
from app.repositories.transaction_repo import TransactionRepository
from app.schemas.admin_payout import (
    DriverEarningsRow,
    EarningsBreakdownResponse,
    MonthlyEarningsPoint,
    PayoutConfirmationResponse,
    PayoutKPIsResponse,
    PayoutScheduleItem,
    SpecialtyPayoutItem,
)
from app.services.admin_payout_service import AdminPayoutService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import PaginatedResponse, StandardResponse

router = APIRouter()


def _get_service(
    session: AsyncSession = Depends(get_db),
    stripe: StripeClient = Depends(get_stripe_client),
    publisher: EventPublisher = Depends(get_publisher),
) -> AdminPayoutService:
    return AdminPayoutService(
        payout_repo=AdminPayoutRepository(session),
        earnings_repo=EarningsRepository(session),
        pm_repo=PaymentMethodRepository(session),
        tx_repo=TransactionRepository(session),
        stripe_client=stripe,
        user_client=UserServiceClient(settings.USER_SERVICE_URL),
        publisher=publisher,
        caregiver_commission_repo=CaregiverCommissionRepository(session),
    )


@router.get(
    "/payouts/kpis",
    response_model=StandardResponse[PayoutKPIsResponse],
)
async def get_payout_kpis(
    is_caregiver: bool = Query(False),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminPayoutService = Depends(_get_service),
):
    """Get payout KPI cards. Filter by is_caregiver for caregiver view."""
    data = await service.get_payout_kpis(is_caregiver=is_caregiver)
    return StandardResponse(data=PayoutKPIsResponse(**data))


@router.get(
    "/payouts/schedule",
    response_model=StandardResponse[list[PayoutScheduleItem]],
)
async def get_payout_schedule(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminPayoutService = Depends(_get_service),
):
    """Get payment schedule timeline."""
    data = await service.get_payout_schedule()
    return StandardResponse(data=[PayoutScheduleItem(**item) for item in data])


@router.get(
    "/payouts/earnings-breakdown",
    response_model=StandardResponse[EarningsBreakdownResponse],
)
async def get_earnings_breakdown(
    is_caregiver: bool = Query(False),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminPayoutService = Depends(_get_service),
):
    """Get earnings breakdown pie chart data."""
    data = await service.get_earnings_breakdown(is_caregiver=is_caregiver)
    return StandardResponse(data=EarningsBreakdownResponse(**data))


@router.get(
    "/payouts/monthly-distribution",
    response_model=StandardResponse[list[MonthlyEarningsPoint]],
)
async def get_monthly_distribution(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminPayoutService = Depends(_get_service),
):
    """Get monthly earnings distribution chart."""
    data = await service.get_monthly_distribution()
    return StandardResponse(data=[MonthlyEarningsPoint(**item) for item in data])


@router.get(
    "/payouts/by-specialty",
    response_model=StandardResponse[list[SpecialtyPayoutItem]],
)
async def get_payouts_by_specialty(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminPayoutService = Depends(_get_service),
):
    """Get payouts grouped by caregiver specialty."""
    specialty_map = await service.build_specialty_map()
    data = await service.get_payouts_by_specialty(specialty_map)
    return StandardResponse(data=[SpecialtyPayoutItem(**item) for item in data])


# Static paths MUST come before /{driver_id}
@router.get(
    "/payouts/drivers",
    response_model=PaginatedResponse[DriverEarningsRow],
)
async def get_driver_earnings_list(
    search: str | None = Query(default=None),
    is_caregiver: bool = Query(False),
    specialty: str | None = Query(default=None),
    fleet_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminPayoutService = Depends(_get_service),
):
    """List driver/caregiver earnings. Use is_caregiver=true for caregiver page."""
    items, total = await service.get_driver_earnings_list(
        search=search,
        is_caregiver=is_caregiver,
        specialty=specialty,
        fleet_id=fleet_id,
        account_status=status,
        page=page,
        limit=limit,
    )
    return PaginatedResponse(
        data=[DriverEarningsRow(**item) for item in items],
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.get(
    "/payouts/drivers/{driver_id}",
    response_model=StandardResponse[PayoutConfirmationResponse],
)
async def get_payout_detail(
    driver_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminPayoutService = Depends(_get_service),
):
    """Get payout confirmation modal data for a driver."""
    data = await service.get_payout_detail(driver_id)
    if not data:
        raise HTTPException(status_code=404, detail="Driver earnings not found")
    return StandardResponse(data=PayoutConfirmationResponse(**data))


@router.post(
    "/payouts/drivers/{driver_id}/pay",
    response_model=StandardResponse[dict],
)
async def process_payout(
    driver_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminPayoutService = Depends(_get_service),
):
    """Execute payout for a driver (Pay Now)."""
    try:
        result = await service.process_payout(driver_id, admin_id=user.id)
        return StandardResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
