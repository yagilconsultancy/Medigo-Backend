from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.payment_service_client import PaymentServiceClient
from app.clients.user_service_client import UserServiceClient
from app.config import settings
from app.dependencies import get_db, get_publisher
from app.repositories.rating_repo import RatingRepository
from app.repositories.recurring_ride_repo import RecurringRideRepository
from app.repositories.ride_repo import RideRepository
from app.repositories.ride_request_repo import RideRequestRepository
from app.repositories.status_log_repo import StatusLogRepository
from app.schemas.ride import (
    DriverContactResponse,
    RebookRideRequest,
    RiderHistoryOverviewResponse,
    RiderStatsResponse,
    RideResponse,
    ShareRideResponse,
    SharedRideResponse,
)
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


@router.get(
    "/rider/me/stats",
    response_model=StandardResponse[RiderStatsResponse],
)
async def get_rider_stats(
    user: UserClaims = Depends(require_role([UserRole.RIDER, UserRole.FACILITY])),
    service: RideService = Depends(_get_ride_service),
):
    """Get rider profile stats (total rides, miles, rating, member since)."""
    stats = await service.get_rider_stats(user.id)
    return StandardResponse(data=RiderStatsResponse(**stats))


@router.get(
    "/rider/me/overview",
    response_model=StandardResponse[RiderHistoryOverviewResponse],
)
async def get_rider_history_overview(
    status: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.RIDER, UserRole.FACILITY])),
    service: RideService = Depends(_get_ride_service),
):
    """Get rider history summary and a filtered ride list."""
    offset = (page - 1) * limit
    data = await service.get_rider_history_overview(user.id, status, offset, limit)

    rides = data["rides"]
    ride_responses = [RideResponse.model_validate(ride) for ride in rides]

    # Collect unique driver and rider IDs for batch fetching
    driver_ids = list({ride.driver_id for ride in rides if ride.driver_id})
    rider_ids = list({ride.rider_id for ride in rides if ride.rider_id})

    # Batch fetch driver and rider profiles
    driver_map: dict = {}
    rider_map: dict = {}

    if driver_ids:
        driver_profiles = await service.user_client.get_drivers_with_details(driver_ids)
        for dp in driver_profiles:
            did = dp.get("id")
            if did:
                driver_map[str(did)] = dp

    if rider_ids:
        rider_profiles = await service.user_client.batch_get_users(rider_ids)
        for rp in rider_profiles:
            rid = rp.get("id")
            if rid:
                rider_map[str(rid)] = rp

    # Enrich each ride response
    for i, ride in enumerate(rides):
        rd = ride_responses[i]

        if ride.driver_id:
            dp = driver_map.get(str(ride.driver_id))
            if dp:
                rd.driver_name = f"{dp.get('first_name', '')} {dp.get('last_name', '')}".strip()
                rd.driver_phone = dp.get('phone')
                rd.driver_avatar_url = dp.get('avatar_url')
                rd.driver_rating = dp.get('rating')
                vehicle = dp.get('vehicle') or dp
                rd.driver_vehicle_type = vehicle.get('vehicle_type')
                rd.driver_vehicle_make = vehicle.get('vehicle_make')
                rd.driver_vehicle_model = vehicle.get('vehicle_model')
                rd.driver_vehicle_color = vehicle.get('vehicle_color')
                rd.driver_vehicle_plate = vehicle.get('vehicle_plate')

        if ride.rider_id:
            rp = rider_map.get(str(ride.rider_id))
            if rp:
                rd.rider_name = f"{rp.get('first_name', '')} {rp.get('last_name', '')}".strip()

    return StandardResponse(
        data=RiderHistoryOverviewResponse(
            summary=data["summary"],
            rides=ride_responses,
            filtered_total=data["filtered_total"],
            page=data["page"],
            limit=data["limit"],
            total_pages=data["total_pages"],
            status_filter=data["status_filter"],
        )
    )


@router.post(
    "/{ride_id}/rebook",
    response_model=StandardResponse[RideResponse],
)
async def rebook_ride(
    ride_id: UUID,
    body: RebookRideRequest,
    user: UserClaims = Depends(require_role([UserRole.RIDER])),
    service: RideService = Depends(_get_ride_service),
):
    """Create a new ride with the same details as a previous ride."""
    ride = await service.rebook_ride(ride_id, user.id, body.scheduled_at)
    return StandardResponse(
        data=RideResponse.model_validate(ride),
        message="Ride rebooked successfully",
    )


@router.post(
    "/{ride_id}/share",
    response_model=StandardResponse[ShareRideResponse],
)
async def share_ride(
    ride_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.RIDER])),
    service: RideService = Depends(_get_ride_service),
):
    """Generate a shareable tracking link for a ride."""
    token = await service.share_ride(ride_id, user.id)
    return StandardResponse(
        data=ShareRideResponse(
            ride_id=ride_id,
            share_token=token,
            share_url=f"{settings.SHARE_BASE_URL}/track/{token}",
        ),
        message="Share link generated",
    )


@router.get(
    "/{ride_id}/driver-contact",
    response_model=StandardResponse[DriverContactResponse],
)
async def get_driver_contact(
    ride_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.RIDER])),
    service: RideService = Depends(_get_ride_service),
):
    """Get the assigned driver's contact information."""
    contact = await service.get_driver_contact(ride_id, user.id)
    return StandardResponse(data=DriverContactResponse(**contact))


@router.get(
    "/{ride_id}/fare",
    response_model=StandardResponse[dict],
)
async def get_ride_fare(
    ride_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.RIDER, UserRole.DRIVER, UserRole.ADMIN, UserRole.FACILITY])),
):
    """Get fare breakdown for a ride from payment-service."""
    payment_client = PaymentServiceClient(settings.PAYMENT_SERVICE_URL)
    fare = await payment_client.get_fare_breakdown(ride_id)
    if not fare:
        return StandardResponse(data={}, message="Fare breakdown not available yet")
    return StandardResponse(data=fare, message="Fare breakdown retrieved")


@router.get(
    "/shared/{share_token}",
    response_model=StandardResponse[SharedRideResponse],
)
async def get_shared_ride(
    share_token: str,
    service: RideService = Depends(_get_ride_service),
):
    """Public endpoint: view a shared ride by token (no auth required)."""
    ride = await service.get_ride_by_share_token(share_token)
    return StandardResponse(
        data=SharedRideResponse.model_validate(ride),
    )
