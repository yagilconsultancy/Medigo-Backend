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
from app.schemas.rating import RatingResponse, SubmitRatingRequest
from app.services.ride_access import ensure_ride_access
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


@router.post("/{ride_id}/rating", response_model=StandardResponse[RatingResponse])
async def submit_rating(
    ride_id: UUID,
    request: SubmitRatingRequest,
    user: UserClaims = Depends(require_role([UserRole.DRIVER, UserRole.RIDER, UserRole.FACILITY])),
    service: RideService = Depends(_get_ride_service),
):
    rating = await service.submit_rating(
        ride_id=ride_id,
        rated_by=user.id,
        rating=request.rating,
        comment=request.comment,
        rating_type=request.rating_type,
    )
    return StandardResponse(
        data=RatingResponse.model_validate(rating),
        message="Rating submitted successfully",
    )


@router.get("/{ride_id}/rating", response_model=StandardResponse[list[RatingResponse]])
async def get_ride_ratings(
    ride_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.DRIVER, UserRole.RIDER, UserRole.ADMIN])),
    service: RideService = Depends(_get_ride_service),
):
    ensure_ride_access(await service.get_ride(ride_id), user)
    ratings = await service.get_ride_ratings(ride_id)
    return StandardResponse(
        data=[RatingResponse.model_validate(r) for r in ratings],
    )
