from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.user_service_client import UserServiceClient
from app.config import settings
from app.dependencies import get_db, get_publisher
from app.repositories.guest_booking_session_repo import GuestBookingSessionRepository
from app.repositories.rating_repo import RatingRepository
from app.repositories.recurring_ride_repo import RecurringRideRepository
from app.repositories.ride_repo import RideRepository
from app.repositories.ride_request_repo import RideRequestRepository
from app.repositories.status_log_repo import StatusLogRepository
from app.schemas.guest_booking import (
    CreateGuestBookingRequest,
    CreateGuestSessionRequest,
    GuestBookingAccessResponse,
    GuestBookingResponse,
    GuestSessionResponse,
)
from app.schemas.ride import RideResponse
from app.services.guest_booking_service import GuestBookingService
from app.services.ride_service import RideService
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.responses import StandardResponse

router = APIRouter(prefix="/public")


def _get_guest_booking_service(
    session: AsyncSession = Depends(get_db),
    publisher: EventPublisher = Depends(get_publisher),
) -> GuestBookingService:
    ride_repo = RideRepository(session)
    ride_service = RideService(
        ride_repo=ride_repo,
        request_repo=RideRequestRepository(session),
        status_log_repo=StatusLogRepository(session),
        rating_repo=RatingRepository(session),
        recurring_ride_repo=RecurringRideRepository(session),
        publisher=publisher,
        user_client=UserServiceClient(settings.USER_SERVICE_URL),
    )
    return GuestBookingService(
        guest_session_repo=GuestBookingSessionRepository(session),
        ride_repo=ride_repo,
        ride_service=ride_service,
        user_client=UserServiceClient(settings.USER_SERVICE_URL),
    )


def _build_guest_booking_access_response(ride) -> GuestBookingAccessResponse:
    return GuestBookingAccessResponse(
        ride=RideResponse.model_validate(ride),
        share_token=ride.share_token,
        share_url=GuestBookingService.build_share_url(ride.share_token),
    )


@router.post("/guest-sessions", response_model=StandardResponse[GuestSessionResponse])
async def create_guest_session(
    body: CreateGuestSessionRequest,
    service: GuestBookingService = Depends(_get_guest_booking_service),
):
    guest_session = await service.create_session(**body.model_dump())
    return StandardResponse(
        data=GuestSessionResponse(
            session_id=guest_session.id,
            rider_id=guest_session.rider_id,
            first_name=guest_session.first_name,
            last_name=guest_session.last_name,
            email=guest_session.email,
            phone=guest_session.phone,
            is_guest=True,
            created_at=guest_session.created_at,
            updated_at=guest_session.updated_at,
            current_booking=None,
        ),
        message="Guest session created",
    )


@router.get("/guest-sessions/{session_id}", response_model=StandardResponse[GuestSessionResponse])
async def get_guest_session(
    session_id: UUID,
    service: GuestBookingService = Depends(_get_guest_booking_service),
):
    guest_session = await service.get_session(session_id)
    latest_ride = await service.get_latest_booking(session_id)
    return StandardResponse(
        data=GuestSessionResponse(
            session_id=guest_session.id,
            rider_id=guest_session.rider_id,
            first_name=guest_session.first_name,
            last_name=guest_session.last_name,
            email=guest_session.email,
            phone=guest_session.phone,
            is_guest=True,
            created_at=guest_session.created_at,
            updated_at=guest_session.updated_at,
            current_booking=(
                _build_guest_booking_access_response(latest_ride)
                if latest_ride
                else None
            ),
        ),
        message="Guest session retrieved",
    )


@router.post("/guest-bookings", response_model=StandardResponse[GuestBookingResponse])
async def create_guest_booking(
    body: CreateGuestBookingRequest,
    service: GuestBookingService = Depends(_get_guest_booking_service),
):
    data = body.model_dump()
    session_id = data.pop("session_id")
    guest_session, ride = await service.create_booking(session_id, **data)
    return StandardResponse(
        data=GuestBookingResponse(
            session_id=guest_session.id,
            rider_id=guest_session.rider_id,
            is_guest=True,
            booking=_build_guest_booking_access_response(ride),
        ),
        message="Guest booking created",
    )


@router.get("/guest-bookings/{ride_id}", response_model=StandardResponse[GuestBookingResponse])
async def get_guest_booking(
    ride_id: UUID,
    session_id: UUID,
    service: GuestBookingService = Depends(_get_guest_booking_service),
):
    guest_session = await service.get_session(session_id)
    ride = await service.get_booking(session_id, ride_id)
    return StandardResponse(
        data=GuestBookingResponse(
            session_id=guest_session.id,
            rider_id=guest_session.rider_id,
            is_guest=True,
            booking=_build_guest_booking_access_response(ride),
        ),
        message="Guest booking retrieved",
    )
