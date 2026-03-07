from uuid import UUID

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
    RideRequestResponse,
    RideResponse,
)
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


@router.get("/requests/pending", response_model=StandardResponse[list[RideRequestResponse]])
async def get_pending_requests(
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: RideService = Depends(_get_ride_service),
):
    enriched = await service.get_pending_requests_for_driver(user.id)
    data = []
    for item in enriched:
        req = item["request"]
        ride = item["ride"]
        data.append(RideRequestResponse(
            id=req.id,
            ride_id=req.ride_id,
            driver_id=req.driver_id,
            status=req.status,
            rider_name=item["rider_name"],
            rider_rating=item["rider_rating"],
            pickup_address=ride.pickup_address,
            destination_address=ride.destination_address,
            ride_type=ride.ride_type,
            estimated_fare=float(ride.estimated_fare) if ride.estimated_fare else None,
            estimated_distance_miles=float(ride.estimated_distance_miles) if ride.estimated_distance_miles else None,
            expires_at=req.expires_at,
        ))
    return StandardResponse(data=data)


@router.put("/requests/{request_id}/accept", response_model=StandardResponse[RideResponse])
async def accept_ride_request(
    request_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: RideService = Depends(_get_ride_service),
):
    ride = await service.accept_ride_request(request_id, user.id)
    return StandardResponse(
        data=RideResponse.model_validate(ride),
        message="Ride request accepted",
    )


@router.put("/requests/{request_id}/decline", response_model=StandardResponse[RideRequestResponse])
async def decline_ride_request(
    request_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: RideService = Depends(_get_ride_service),
):
    req = await service.decline_ride_request(request_id, user.id)
    # Return minimal response
    return StandardResponse(
        data=RideRequestResponse(
            id=req.id,
            ride_id=req.ride_id,
            driver_id=req.driver_id,
            status=req.status,
            rider_name="",
            rider_rating=0,
            pickup_address="",
            destination_address="",
            ride_type="",
            expires_at=req.expires_at,
        ),
        message="Ride request declined",
    )
