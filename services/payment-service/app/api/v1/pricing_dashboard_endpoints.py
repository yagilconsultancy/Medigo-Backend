from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.pricing_dashboard import (
    PricingDashboardKPIs,
    PricingHealthResponse,
    RecentChangesResponse,
    RouteComparisonResponse,
)
from app.services.pricing_dashboard_service import PricingDashboardService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> PricingDashboardService:
    return PricingDashboardService(session)


@router.get("/dashboard/kpis", response_model=StandardResponse[PricingDashboardKPIs])
async def get_dashboard_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: PricingDashboardService = Depends(_get_service),
):
    data = await service.get_kpis()
    return StandardResponse(data=PricingDashboardKPIs(**data))


@router.get("/dashboard/route-comparison", response_model=StandardResponse[RouteComparisonResponse])
async def get_route_comparison(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: PricingDashboardService = Depends(_get_service),
):
    routes = await service.get_route_comparison()
    return StandardResponse(data=RouteComparisonResponse(routes=routes))


@router.get("/dashboard/recent-changes", response_model=StandardResponse[RecentChangesResponse])
async def get_recent_changes(
    limit: int = Query(default=10, le=50),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: PricingDashboardService = Depends(_get_service),
):
    changes = await service.get_recent_changes(limit=limit)
    return StandardResponse(data=RecentChangesResponse(changes=changes))


@router.get("/dashboard/health", response_model=StandardResponse[PricingHealthResponse])
async def get_pricing_health(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: PricingDashboardService = Depends(_get_service),
):
    items = await service.get_health()
    return StandardResponse(data=PricingHealthResponse(items=items))
