from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.ride_service_client import RideServiceClient
from app.clients.user_service_client import UserServiceClient
from app.config import settings
from app.dependencies import get_db
from app.repositories.location_history_repo import LocationHistoryRepository
from app.repositories.tracking_session_repo import TrackingSessionRepository
from app.schemas.admin_tracking import (
    ActiveTripDetail,
    ActiveTripKPIs,
    ActiveTripOverview,
    LiveDriverEntry,
)
from app.services.admin_tracking_service import AdminTrackingService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_admin_tracking_service(
    session: AsyncSession = Depends(get_db),
) -> AdminTrackingService:
    return AdminTrackingService(
        session_repo=TrackingSessionRepository(session),
        history_repo=LocationHistoryRepository(session),
        ride_client=RideServiceClient(settings.RIDE_SERVICE_URL),
        user_client=UserServiceClient(settings.USER_SERVICE_URL),
    )


@router.get("/kpis", response_model=StandardResponse[ActiveTripKPIs])
async def get_active_trip_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminTrackingService = Depends(_get_admin_tracking_service),
):
    """Get KPI metrics for the active trip monitoring dashboard."""
    kpis = await service.get_active_trip_kpis()
    return StandardResponse(data=kpis, message="Active trip KPIs retrieved")


@router.get("/trips", response_model=StandardResponse[list[ActiveTripOverview]])
async def get_active_trips(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminTrackingService = Depends(_get_admin_tracking_service),
):
    """Get all active trips with driver/rider enrichment for the map."""
    trips = await service.get_active_trips()
    return StandardResponse(data=trips, message="Active trips retrieved")


@router.get("/trips/{ride_id}", response_model=StandardResponse[ActiveTripDetail])
async def get_trip_detail(
    ride_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminTrackingService = Depends(_get_admin_tracking_service),
):
    """Get detailed tracking info for a specific trip including route history."""
    detail = await service.get_trip_detail(ride_id)
    if not detail:
        raise HTTPException(status_code=404, detail="No active tracking session for this ride")
    return StandardResponse(data=detail, message="Trip detail retrieved")


@router.get("/live-drivers", response_model=StandardResponse[list[LiveDriverEntry]])
async def get_live_drivers(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminTrackingService = Depends(_get_admin_tracking_service),
):
    """Get all active drivers with current positions for the live driver map."""
    drivers = await service.get_live_drivers()
    return StandardResponse(data=drivers, message="Live drivers retrieved")
