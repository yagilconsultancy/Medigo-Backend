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
    AdminAssignDriverRequest,
    AssignBusinessRequest,
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


@router.get("/rides/pending", response_model=PaginatedResponse[RideResponse])
async def get_pending_rides(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: RideService = Depends(_get_ride_service),
):
    """Get all REQUESTED rides awaiting admin assignment."""
    offset = (page - 1) * limit
    rides, total = await service.get_pending_admin_rides(offset, limit)
    return PaginatedResponse(
        data=[RideResponse.model_validate(r) for r in rides],
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.put(
    "/rides/{ride_id}/assign-business",
    response_model=StandardResponse[RideResponse],
)
async def assign_ride_to_business(
    ride_id: UUID,
    body: AssignBusinessRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: RideService = Depends(_get_ride_service),
):
    """Assign a ride to a business fleet for fulfillment."""
    ride = await service.assign_ride_to_business(
        ride_id, body.business_id, user.id, body.expiry_minutes
    )
    return StandardResponse(
        data=RideResponse.model_validate(ride),
        message="Ride assigned to business",
    )


@router.put(
    "/rides/{ride_id}/assign-driver",
    response_model=StandardResponse[RideResponse],
)
async def admin_assign_driver(
    ride_id: UUID,
    body: AdminAssignDriverRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: RideService = Depends(_get_ride_service),
):
    """Admin directly assigns a driver (typically for ambulatory rides)."""
    ride = await service.admin_assign_driver(ride_id, body.driver_id, user.id)
    return StandardResponse(
        data=RideResponse.model_validate(ride),
        message="Driver assigned by admin",
    )


@router.get("/rides", response_model=PaginatedResponse[RideResponse])
async def get_all_rides(
    status: str | None = None,
    ride_type: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: RideService = Depends(_get_ride_service),
):
    """Admin dashboard: get all rides with optional filters."""
    offset = (page - 1) * limit
    rides, total = await service.get_all_rides_admin(status, ride_type, offset, limit)
    return PaginatedResponse(
        data=[RideResponse.model_validate(r) for r in rides],
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )
