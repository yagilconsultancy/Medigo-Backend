from fastapi import APIRouter, Depends

from app.api.v1.rider_endpoints import _get_ride_service
from app.schemas.ride import PublicTripViewResponse
from app.services.ride_service import RideService
from mediride_common.schemas.responses import StandardResponse

router = APIRouter(prefix="/public/track")


@router.get(
    "/{share_token}",
    response_model=StandardResponse[PublicTripViewResponse],
)
async def get_public_trip_view(
    share_token: str,
    service: RideService = Depends(_get_ride_service),
):
    """Public, read-only trip view for a share link (no login).

    Unknown or expired tokens return 404. Live driver details and position
    are only included while the ride is active.
    """
    view = await service.get_public_trip_view(share_token)
    return StandardResponse(data=PublicTripViewResponse(**view))
