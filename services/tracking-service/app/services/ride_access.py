"""Who may read a ride's live tracking data over REST.

Mirrors the participant rule the Socket.IO join already uses: admins see every
ride, everyone else only rides they take part in (rider, assigned driver or
caregiver). A caller who is not a participant gets the same 404 as a ride that
does not exist, so ride ids cannot be probed.
"""

from uuid import UUID

from app.clients.ride_service_client import RideServiceClient
from app.config import settings
from mediride_common.auth.models import UserClaims
from mediride_common.exceptions import NotFoundError
from mediride_common.schemas.enums import UserRole


def is_ride_participant(user: UserClaims, ride: dict) -> bool:
    if user.role == UserRole.ADMIN:
        return True
    user_id = str(user.id)
    participants = {
        str(ride.get(key))
        for key in ("rider_id", "driver_id", "caregiver_id")
        if ride.get(key)
    }
    return user_id in participants


async def ensure_can_view_ride(user: UserClaims, ride_id: UUID) -> None:
    if user.role == UserRole.ADMIN:
        return
    ride = await RideServiceClient(settings.RIDE_SERVICE_URL).get_ride(ride_id)
    if not ride or not is_ride_participant(user, ride):
        raise NotFoundError("Ride not found")
