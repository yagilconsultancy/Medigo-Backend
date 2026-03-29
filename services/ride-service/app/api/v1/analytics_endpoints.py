from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.payment_service_client import PaymentServiceClient
from app.clients.user_service_client import UserServiceClient
from app.config import settings
from app.dependencies import get_db
from app.repositories.analytics_repo import AnalyticsRepository
from app.schemas.analytics import (
    DashboardKPIs,
    RecentActivityResponse,
    TopDriversResponse,
    TripStatusDistributionResponse,
    TripVolumeTrendResponse,
)
from app.services.analytics_service import AnalyticsService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _analytics_service(session: AsyncSession) -> AnalyticsService:
    return AnalyticsService(
        analytics_repo=AnalyticsRepository(session),
        user_client=UserServiceClient(settings.USER_SERVICE_URL),
        payment_client=PaymentServiceClient(settings.PAYMENT_SERVICE_URL),
    )


def _resolve_fleet_id(user: UserClaims) -> str | None:
    """ADMIN sees all data; fleet managers see only their fleet."""
    if user.role == UserRole.BUSINESS:
        return user.business_id
    return None


@router.get("/overview", response_model=StandardResponse[DashboardKPIs])
async def get_dashboard_overview(
    user: UserClaims = Depends(require_role([UserRole.ADMIN, UserRole.BUSINESS])),
    session: AsyncSession = Depends(get_db),
):
    """Dashboard KPI cards: total trips, active drivers, pending bookings, revenue."""
    svc = _analytics_service(session)
    kpis = await svc.get_dashboard_kpis(business_id=_resolve_fleet_id(user))
    return StandardResponse(data=kpis)


@router.get("/trip-volume", response_model=StandardResponse[TripVolumeTrendResponse])
async def get_trip_volume_trend(
    days: int = Query(default=30, ge=7, le=90),
    user: UserClaims = Depends(require_role([UserRole.ADMIN, UserRole.BUSINESS])),
    session: AsyncSession = Depends(get_db),
):
    """Trip volume trend for the last N days (7, 30, or 90)."""
    svc = _analytics_service(session)
    trend = await svc.get_trip_volume_trend(
        days=days, business_id=_resolve_fleet_id(user)
    )
    return StandardResponse(data=trend)


@router.get("/trip-status", response_model=StandardResponse[TripStatusDistributionResponse])
async def get_trip_status_distribution(
    user: UserClaims = Depends(require_role([UserRole.ADMIN, UserRole.BUSINESS])),
    session: AsyncSession = Depends(get_db),
):
    """Trip status distribution (pie chart data)."""
    svc = _analytics_service(session)
    dist = await svc.get_trip_status_distribution(
        business_id=_resolve_fleet_id(user)
    )
    return StandardResponse(data=dist)


@router.get("/top-drivers", response_model=StandardResponse[TopDriversResponse])
async def get_top_drivers(
    days: int = Query(default=30, ge=7, le=90),
    limit: int = Query(default=5, ge=1, le=20),
    user: UserClaims = Depends(require_role([UserRole.ADMIN, UserRole.BUSINESS])),
    session: AsyncSession = Depends(get_db),
):
    """Top performing drivers ranked by completed trips with average rating."""
    svc = _analytics_service(session)
    top = await svc.get_top_drivers(
        days=days, limit=limit, business_id=_resolve_fleet_id(user)
    )
    return StandardResponse(data=top)


@router.get("/recent-activity", response_model=StandardResponse[RecentActivityResponse])
async def get_recent_activity(
    limit: int = Query(default=20, ge=1, le=50),
    user: UserClaims = Depends(require_role([UserRole.ADMIN, UserRole.BUSINESS])),
    session: AsyncSession = Depends(get_db),
):
    """Recent activity feed (latest status transitions across all rides)."""
    svc = _analytics_service(session)
    activity = await svc.get_recent_activity(
        limit=limit, business_id=_resolve_fleet_id(user)
    )
    return StandardResponse(data=activity)
