from mediride_common.auth.models import UserClaims
from mediride_common.exceptions import NotFoundError
from mediride_common.schemas.enums import UserRole


def can_access_ride(ride, user: UserClaims) -> bool:
    """Whether this user may see or act on the ride.

    Admins see every ride. A driver only the ride they are assigned to. A rider
    or facility only rides they booked (facilities book under their own user id)
    and the caregiver attached to the ride.
    """
    if user.role == UserRole.ADMIN:
        return True
    if user.role == UserRole.DRIVER:
        return ride.driver_id is not None and ride.driver_id == user.id
    if user.role in (UserRole.RIDER, UserRole.FACILITY):
        return ride.rider_id == user.id or (
            ride.caregiver_id is not None and ride.caregiver_id == user.id
        )
    return False


def ensure_ride_access(ride, user: UserClaims) -> None:
    """Raise a 404 when the user may not access the ride.

    404 rather than 403 so ride ids cannot be probed for existence.
    """
    if not can_access_ride(ride, user):
        raise NotFoundError("Ride not found")
