from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.payment_service_client import PaymentServiceClient
from app.clients.user_service_client import UserServiceClient
from app.config import settings
from app.dependencies import get_db
from app.repositories.analytics_repo import AnalyticsRepository
from app.schemas.analytics import (
    BookingChannelsResponse,
    DashboardKPIs,
    RecentActivityResponse,
    ServiceQualityResponse,
    TopDriversResponse,
    TopFacilitiesResponse,
    TopFleetPartnersResponse,
    TransportDistributionResponse,
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


@router.get(
    "/transport-distribution",
    response_model=StandardResponse[TransportDistributionResponse],
)
async def get_transport_distribution(
    days: int = Query(default=30, ge=7, le=90),
    user: UserClaims = Depends(require_role([UserRole.ADMIN, UserRole.BUSINESS])),
    session: AsyncSession = Depends(get_db),
):
    """Transport type distribution (Wheelchair, Stretcher, Ambulatory) + booking source split."""
    svc = _analytics_service(session)
    dist = await svc.get_transport_distribution(
        days=days, business_id=_resolve_fleet_id(user)
    )
    return StandardResponse(data=dist)


@router.get(
    "/top-fleet-partners",
    response_model=StandardResponse[TopFleetPartnersResponse],
)
async def get_top_fleet_partners(
    days: int = Query(default=30, ge=7, le=90),
    limit: int = Query(default=6, ge=1, le=20),
    user: UserClaims = Depends(require_role([UserRole.ADMIN, UserRole.BUSINESS])),
    session: AsyncSession = Depends(get_db),
):
    """Top fleet partners ranked by completed trips with vehicle count and rating."""
    svc = _analytics_service(session)
    top = await svc.get_top_fleet_partners(
        days=days, limit=limit, business_id=_resolve_fleet_id(user)
    )
    return StandardResponse(data=top)


@router.get(
    "/booking-channels",
    response_model=StandardResponse[BookingChannelsResponse],
)
async def get_booking_channels(
    days: int = Query(default=30, ge=7, le=90),
    user: UserClaims = Depends(require_role([UserRole.ADMIN, UserRole.BUSINESS])),
    session: AsyncSession = Depends(get_db),
):
    """Booking channel breakdown (Mobile App, Website Client, Website Facility)."""
    svc = _analytics_service(session)
    channels = await svc.get_booking_channels(
        days=days, business_id=_resolve_fleet_id(user)
    )
    return StandardResponse(data=channels)


@router.get(
    "/service-quality",
    response_model=StandardResponse[ServiceQualityResponse],
)
async def get_service_quality(
    user: UserClaims = Depends(require_role([UserRole.ADMIN, UserRole.BUSINESS])),
    session: AsyncSession = Depends(get_db),
):
    """Service quality metrics: avg pickup time, trip distance, rating, completion rate."""
    svc = _analytics_service(session)
    quality = await svc.get_service_quality(
        business_id=_resolve_fleet_id(user)
    )
    return StandardResponse(data=quality)


@router.get(
    "/top-facilities",
    response_model=StandardResponse[TopFacilitiesResponse],
)
async def get_top_facilities(
    days: int = Query(default=30, ge=7, le=90),
    limit: int = Query(default=5, ge=1, le=20),
    user: UserClaims = Depends(require_role([UserRole.ADMIN, UserRole.BUSINESS])),
    session: AsyncSession = Depends(get_db),
):
    """Top performing facilities ranked by total bookings with acceptance rate."""
    svc = _analytics_service(session)
    facilities = await svc.get_top_facilities(
        days=days, limit=limit, business_id=_resolve_fleet_id(user)
    )
    return StandardResponse(data=facilities)
