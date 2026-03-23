from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories.admin_revenue_repo import AdminRevenueRepository
from app.schemas.admin_revenue import (
    RevenueByCityItem,
    RevenueByRideTypeItem,
    RevenueDistributionResponse,
    RevenueKPIsResponse,
    RevenueTrendPoint,
)
from app.services.admin_revenue_service import AdminRevenueService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> AdminRevenueService:
    return AdminRevenueService(
        revenue_repo=AdminRevenueRepository(session),
    )


@router.get(
    "/revenue/kpis",
    response_model=StandardResponse[RevenueKPIsResponse],
)
async def get_revenue_kpis(
    period: str = Query("daily", description="daily|monthly|yearly"),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRevenueService = Depends(_get_service),
):
    """Get revenue KPI cards based on period."""
    data = await service.get_revenue_kpis(period)
    return StandardResponse(data=RevenueKPIsResponse(**data))


@router.get(
    "/revenue/trend",
    response_model=StandardResponse[list[RevenueTrendPoint]],
)
async def get_revenue_trend(
    period: str = Query("daily", description="daily|monthly|yearly"),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRevenueService = Depends(_get_service),
):
    """Get revenue trend chart data."""
    data = await service.get_revenue_trend(period)
    return StandardResponse(data=[RevenueTrendPoint(**item) for item in data])


@router.get(
    "/revenue/by-ride-type",
    response_model=StandardResponse[list[RevenueByRideTypeItem]],
)
async def get_revenue_by_ride_type(
    period: str = Query("daily", description="daily|monthly|yearly"),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRevenueService = Depends(_get_service),
):
    """Get revenue grouped by ride type."""
    data = await service.get_revenue_by_ride_type(period)
    return StandardResponse(data=[RevenueByRideTypeItem(**item) for item in data])


@router.get(
    "/revenue/by-city",
    response_model=StandardResponse[list[RevenueByCityItem]],
)
async def get_revenue_by_city(
    period: str = Query("daily", description="daily|monthly|yearly"),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRevenueService = Depends(_get_service),
):
    """Get revenue ranked by city."""
    data = await service.get_revenue_by_city(period)
    return StandardResponse(data=[RevenueByCityItem(**item) for item in data])


@router.get(
    "/revenue/distribution",
    response_model=StandardResponse[RevenueDistributionResponse],
)
async def get_revenue_distribution(
    period: str = Query("daily", description="daily|monthly|yearly"),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRevenueService = Depends(_get_service),
):
    """Get revenue distribution (pie chart data)."""
    data = await service.get_revenue_distribution(period)
    return StandardResponse(data=RevenueDistributionResponse(**data))
