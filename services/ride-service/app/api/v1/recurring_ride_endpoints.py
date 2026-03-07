from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.user_service_client import UserServiceClient
from app.config import settings
from app.dependencies import get_db, get_publisher
from app.repositories.rating_repo import RatingRepository
from app.repositories.recurring_ride_repo import RecurringRideRepository
from app.repositories.ride_repo import RideRepository
from app.repositories.ride_request_repo import RideRequestRepository
from app.repositories.status_log_repo import StatusLogRepository
from app.schemas.ride import CreateRecurringRideRequest, RecurringRideResponse
from app.services.ride_service import RideService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

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


@router.post("/", response_model=StandardResponse[RecurringRideResponse])
async def create_recurring_ride(
    request: CreateRecurringRideRequest,
    user: UserClaims = Depends(require_role([UserRole.RIDER, UserRole.BUSINESS])),
    service: RideService = Depends(_get_ride_service),
):
    recurring = await service.create_recurring_ride(
        rider_id=user.id,
        **request.model_dump(),
    )
    return StandardResponse(
        data=RecurringRideResponse.model_validate(recurring),
        message="Recurring ride created",
    )


@router.get("/", response_model=StandardResponse[list[RecurringRideResponse]])
async def list_recurring_rides(
    user: UserClaims = Depends(require_role([UserRole.RIDER])),
    service: RideService = Depends(_get_ride_service),
):
    rides = await service.get_recurring_rides(user.id)
    return StandardResponse(
        data=[RecurringRideResponse.model_validate(r) for r in rides],
    )


@router.delete("/{recurring_ride_id}", response_model=StandardResponse)
async def deactivate_recurring_ride(
    recurring_ride_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.RIDER])),
    service: RideService = Depends(_get_ride_service),
):
    await service.deactivate_recurring_ride(recurring_ride_id, user.id)
    return StandardResponse(message="Recurring ride deactivated")
