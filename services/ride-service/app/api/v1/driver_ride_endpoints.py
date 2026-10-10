from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.user_service_client import UserServiceClient
from app.config import settings
from app.dependencies import get_db, get_publisher
from app.repositories.rating_repo import RatingRepository
from app.repositories.recurring_ride_repo import RecurringRideRepository
from app.repositories.ride_repo import RideRepository
from app.repositories.ride_request_repo import RideRequestRepository
from app.repositories.status_log_repo import StatusLogRepository
from app.schemas.ride import (
    DriverStatsResponse,
    RideResponse,
)
from app.schemas.rating import DriverRatingsResponse
from app.services.ride_service import RideService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import PaginatedResponse, StandardResponse

router = APIRouter()


def _get_ride_service(
    session: AsyncSession = Depends(get_db),
    publisher: EventPublisher = Depends(get_publisher),
) -> RideService:
    return RideService(
        ride_repo=RideRepository(session),
        request_repo=RideRequestRepository(session),
        status_log_repo=StatusLogRepository(session),
        rating_repo=RatingRepository(session),
        recurring_ride_repo=RecurringRideRepository(session),
        publisher=publisher,
        user_client=UserServiceClient(settings.USER_SERVICE_URL),
    )


@router.get("/upcoming", response_model=PaginatedResponse[RideResponse])
async def get_upcoming_rides(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: RideService = Depends(_get_ride_service),
):
    offset = (page - 1) * limit
    rides, total = await service.get_upcoming_rides_for_driver(user.id, offset, limit)
    return PaginatedResponse(
        data=[RideResponse.model_validate(r) for r in rides],
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.get("/trips", response_model=PaginatedResponse[RideResponse])
async def get_driver_trips(
    status: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: RideService = Depends(_get_ride_service),
):
    offset = (page - 1) * limit
    rides, total = await service.get_driver_trips(user.id, status, offset, limit)
    return PaginatedResponse(
        data=[RideResponse.model_validate(r) for r in rides],
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.get("/stats", response_model=StandardResponse[DriverStatsResponse])
async def get_driver_stats(
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: RideService = Depends(_get_ride_service),
):
    stats = await service.get_driver_stats(user.id)
    return StandardResponse(data=DriverStatsResponse(**stats))


@router.get("/ratings", response_model=StandardResponse[DriverRatingsResponse])
async def get_my_ratings(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: RideService = Depends(_get_ride_service),
):
    """The driver's own real ratings. No rider identity is returned."""
    data = await service.get_driver_ratings(user.id, (page - 1) * limit, limit)
    return StandardResponse(data=DriverRatingsResponse(**data))
