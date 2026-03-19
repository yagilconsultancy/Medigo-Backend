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
    BusinessAssignDriverRequest,
    BusinessRejectRequest,
    RideResponse,
)
from app.services.ride_service import RideService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.events.publisher import EventPublisher
from mediride_common.exceptions import ValidationError
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


def _get_business_id(user: UserClaims) -> UUID:
    """Extract business_id from user claims, raise if not available."""
    if not user.business_id:
        raise ValidationError("No business associated with your account")
    return user.business_id


@router.get("/rides/pending", response_model=PaginatedResponse[RideResponse])
async def get_pending_business_rides(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.BUSINESS, UserRole.ADMIN])),
    service: RideService = Depends(_get_ride_service),
):
    """Get rides assigned to my business awaiting acceptance."""
    business_id = _get_business_id(user)
    offset = (page - 1) * limit
    rides, total = await service.get_pending_business_rides(business_id, offset, limit)
    return PaginatedResponse(
        data=[RideResponse.model_validate(r) for r in rides],
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.put("/rides/{ride_id}/accept", response_model=StandardResponse[RideResponse])
async def business_accept_ride(
    ride_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.BUSINESS, UserRole.ADMIN])),
    service: RideService = Depends(_get_ride_service),
):
    """Business accepts a ride assignment from admin."""
    business_id = _get_business_id(user)
    ride = await service.business_accept_ride(ride_id, business_id)
    return StandardResponse(
        data=RideResponse.model_validate(ride),
        message="Ride accepted",
    )


@router.put("/rides/{ride_id}/reject", response_model=StandardResponse[RideResponse])
async def business_reject_ride(
    ride_id: UUID,
    body: BusinessRejectRequest,
    user: UserClaims = Depends(require_role([UserRole.BUSINESS, UserRole.ADMIN])),
    service: RideService = Depends(_get_ride_service),
):
    """Business rejects a ride assignment; ride returns to admin queue."""
    business_id = _get_business_id(user)
    ride = await service.business_reject_ride(ride_id, business_id, body.reason)
    return StandardResponse(
        data=RideResponse.model_validate(ride),
        message="Ride rejected, returned to admin queue",
    )


@router.put(
    "/rides/{ride_id}/assign-driver",
    response_model=StandardResponse[RideResponse],
)
async def business_assign_driver(
    ride_id: UUID,
    body: BusinessAssignDriverRequest,
    user: UserClaims = Depends(require_role([UserRole.BUSINESS, UserRole.ADMIN])),
    service: RideService = Depends(_get_ride_service),
):
    """Business assigns one of their drivers to a confirmed ride."""
    business_id = _get_business_id(user)
    ride = await service.business_assign_driver(ride_id, body.driver_id, business_id)
    return StandardResponse(
        data=RideResponse.model_validate(ride),
        message="Driver assigned",
    )


@router.get("/rides", response_model=PaginatedResponse[RideResponse])
async def get_business_rides(
    status: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.BUSINESS, UserRole.ADMIN])),
    service: RideService = Depends(_get_ride_service),
):
    """Get all rides assigned to my business."""
    business_id = _get_business_id(user)
    offset = (page - 1) * limit
    rides, total = await service.get_business_rides(business_id, status, offset, limit)
    return PaginatedResponse(
        data=[RideResponse.model_validate(r) for r in rides],
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )
