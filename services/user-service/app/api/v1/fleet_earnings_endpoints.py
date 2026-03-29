from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.payment_service_client import PaymentServiceClient
from app.config import settings
from app.dependencies import get_db
from app.repositories.fleet_repo import FleetRepository
from app.schemas.fleet_earnings import (
    FleetEarningsBreakdownRow,
    FleetEarningsKPIs,
    FleetRevenueTrendResponse,
)
from app.services.fleet_earnings_service import FleetEarningsService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import PaginatedResponse, StandardResponse

router = APIRouter()


def _get_service(
    session: AsyncSession = Depends(get_db),
) -> FleetEarningsService:
    return FleetEarningsService(
        payment_client=PaymentServiceClient(settings.PAYMENT_SERVICE_URL),
        fleet_repo=FleetRepository(session),
    )


@router.get(
    "/admin/fleet/earnings/kpis",
    response_model=StandardResponse[FleetEarningsKPIs],
)
async def get_earnings_kpis(
    fleet_id: UUID | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetEarningsService = Depends(_get_service),
):
    kpis = await service.get_earnings_kpis(fleet_id=fleet_id, days=days)
    return StandardResponse(data=kpis)


@router.get(
    "/admin/fleet/earnings/trend",
    response_model=StandardResponse[FleetRevenueTrendResponse],
)
async def get_revenue_trend(
    fleet_id: UUID | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetEarningsService = Depends(_get_service),
):
    trend = await service.get_revenue_trend(fleet_id=fleet_id, days=days)
    return StandardResponse(data=trend)


@router.get(
    "/admin/fleet/earnings/breakdown",
    response_model=PaginatedResponse[FleetEarningsBreakdownRow],
)
async def get_earnings_breakdown(
    fleet_id: UUID | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FleetEarningsService = Depends(_get_service),
):
    offset = (page - 1) * limit
    rows, total = await service.get_earnings_breakdown(
        fleet_id=fleet_id, days=days, offset=offset, limit=limit
    )
    return PaginatedResponse(
        data=rows,
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )
