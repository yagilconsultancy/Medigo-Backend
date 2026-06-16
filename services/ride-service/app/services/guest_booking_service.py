from uuid import UUID

from app.clients.user_service_client import UserServiceClient
from app.config import settings
from app.models.guest_booking_session import GuestBookingSession
from app.repositories.guest_booking_session_repo import GuestBookingSessionRepository
from app.repositories.ride_repo import RideRepository
from app.services.ride_service import RideService
from mediride_common.exceptions import NotFoundError, ValidationError


class GuestBookingService:
    def __init__(
        self,
        guest_session_repo: GuestBookingSessionRepository,
        ride_repo: RideRepository,
        ride_service: RideService,
        user_client: UserServiceClient,
    ):
        self.guest_session_repo = guest_session_repo
        self.ride_repo = ride_repo
        self.ride_service = ride_service
        self.user_client = user_client

    async def create_session(
        self,
        *,
        email: str | None = None,
        phone: str | None = None,
        full_name: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> GuestBookingSession:
        guest_rider = await self.user_client.create_guest_rider(
            email=email,
            phone=phone,
            full_name=full_name,
            first_name=first_name,
            last_name=last_name,
        )
        if not guest_rider:
            raise ValidationError("Unable to create guest rider profile")

        guest_session = GuestBookingSession(
            rider_id=UUID(guest_rider["user_id"]),
            first_name=guest_rider.get("first_name", "") or "",
            last_name=guest_rider.get("last_name", "") or "",
            email=guest_rider.get("email"),
            phone=guest_rider.get("phone"),
        )
        return await self.guest_session_repo.create(guest_session)

    async def get_session(self, session_id: UUID) -> GuestBookingSession:
        guest_session = await self.guest_session_repo.get_by_id(session_id)
        if not guest_session:
            raise NotFoundError("Guest session not found")
        return guest_session

    async def create_booking(self, session_id: UUID, **ride_data):
        guest_session = await self.get_session(session_id)
        ride_data.setdefault("booking_channel", "website_guest")
        ride = await self.ride_service.create_ride(
            rider_id=guest_session.rider_id,
            guest_session_id=guest_session.id,
            **ride_data,
        )
        return guest_session, ride

    async def get_latest_booking(self, session_id: UUID):
        await self.get_session(session_id)
        return await self.ride_repo.get_latest_by_guest_session(session_id)

    async def get_all_bookings(self, session_id: UUID):
        await self.get_session(session_id)
        return await self.ride_repo.get_all_by_guest_session(session_id)

    async def get_booking(self, session_id: UUID, ride_id: UUID):
        await self.get_session(session_id)
        ride = await self.ride_repo.get_by_guest_session_and_ride_id(session_id, ride_id)
        if not ride:
            raise NotFoundError("Guest booking not found")
        return ride

    @staticmethod
    def build_share_url(share_token: str | None) -> str | None:
        if not share_token:
            return None
        return f"{settings.SHARE_BASE_URL}/track/{share_token}"
