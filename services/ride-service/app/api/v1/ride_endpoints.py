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
from app.schemas.rating import RatingResponse
from app.schemas.ride import (
    CancelRideRequest,
    CreateRideRequest,
    RideDetailResponse,
    RideResponse,
    StatusLogResponse,
    StatusTransitionRequest,
)
from app.services.ride_service import RideService
from mediride_common.auth.dependencies import get_current_user, require_role
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


@router.post("/", response_model=StandardResponse[RideResponse])
async def create_ride(
    request: CreateRideRequest,
    user: UserClaims = Depends(
        require_role([UserRole.RIDER, UserRole.BUSINESS, UserRole.ADMIN, UserRole.FACILITY])
    ),
    service: RideService = Depends(_get_ride_service),
):
    data = request.model_dump()
    # Auto-set facility fields when booked by a facility user
    if user.role == UserRole.FACILITY:
        data["facility_id"] = user.id
        if data.get("booking_channel") == "mobile_app":
            data["booking_channel"] = "website_facility"
    ride = await service.create_ride(
        rider_id=user.id,
        **data,
    )
    return StandardResponse(
        data=RideResponse.model_validate(ride),
        message="Ride created successfully",
    )


@router.get("/rider/me", response_model=PaginatedResponse[RideResponse])
async def get_my_rides(
    status: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.RIDER, UserRole.FACILITY])),
    service: RideService = Depends(_get_ride_service),
):
    offset = (page - 1) * limit
    rides, total = await service.get_rider_trips(user.id, status, offset, limit)
    ride_responses = [RideResponse.model_validate(r) for r in rides]

    # Batch fetch driver and rider profiles for enrichment
    driver_ids = list({ride.driver_id for ride in rides if ride.driver_id})
    rider_ids = list({ride.rider_id for ride in rides if ride.rider_id})

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

    return PaginatedResponse(
        data=ride_responses,
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.get("/rider/me/active", response_model=StandardResponse[RideResponse | None])
async def get_my_active_ride(
    user: UserClaims = Depends(require_role([UserRole.RIDER])),
    service: RideService = Depends(_get_ride_service),
):
    """Get rider's current active ride (excludes cancelled, completed, no-show)."""
    ride = await service.get_active_ride_for_rider(user.id)

    if not ride:
        return StandardResponse(
            data=None,
            message="No active ride",
        )

    # Build base response
    ride_data = RideResponse.model_validate(ride)

    # Enrich with rider name
    rider_profile = await service.user_client.get_user_profile(ride.rider_id)
    if rider_profile:
        ride_data.rider_name = f"{rider_profile.get('first_name', '')} {rider_profile.get('last_name', '')}".strip()

    # Enrich with driver details if driver is assigned
    if ride.driver_id:
        driver_profile = await service.user_client.get_driver_profile(ride.driver_id)
        if driver_profile:
            ride_data.driver_name = f"{driver_profile.get('first_name', '')} {driver_profile.get('last_name', '')}".strip()
            ride_data.driver_phone = driver_profile.get('phone')
            ride_data.driver_avatar_url = driver_profile.get('avatar_url')
            ride_data.driver_rating = driver_profile.get('rating')
            ride_data.driver_vehicle_type = driver_profile.get('vehicle_type')
            ride_data.driver_vehicle_make = driver_profile.get('vehicle_make')
            ride_data.driver_vehicle_model = driver_profile.get('vehicle_model')
            ride_data.driver_vehicle_color = driver_profile.get('vehicle_color')
            ride_data.driver_vehicle_plate = driver_profile.get('vehicle_plate')

    return StandardResponse(
        data=ride_data,
        message="Active ride retrieved",
    )


@router.get("/driver/me", response_model=PaginatedResponse[RideResponse])
async def get_driver_rides(
    status: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: RideService = Depends(_get_ride_service),
):
    """Get all rides assigned to this driver."""
    offset = (page - 1) * limit
    rides, total = await service.get_driver_trips(user.id, status, offset, limit)
    return PaginatedResponse(
        data=[RideResponse.model_validate(r) for r in rides],
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.get("/driver/me/active", response_model=StandardResponse[RideResponse | None])
async def get_driver_active_ride(
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: RideService = Depends(_get_ride_service),
):
    """Get driver's current active ride (excludes cancelled, completed, no-show)."""
    ride = await service.get_active_ride_for_driver(user.id)
    return StandardResponse(
        data=RideResponse.model_validate(ride) if ride else None,
        message="Active ride retrieved" if ride else "No active ride",
    )


@router.get("/{ride_id}", response_model=StandardResponse[RideDetailResponse])
async def get_ride_detail(
    ride_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.DRIVER, UserRole.RIDER, UserRole.ADMIN, UserRole.FACILITY])),
    service: RideService = Depends(_get_ride_service),
):
    detail = await service.get_ride_detail(ride_id)
    ride = detail["ride"]
    return StandardResponse(
        data=RideDetailResponse(
            **{k: getattr(ride, k) for k in RideResponse.model_fields if hasattr(ride, k)},
            pickup_latitude=float(ride.pickup_latitude) if ride.pickup_latitude else None,
            pickup_longitude=float(ride.pickup_longitude) if ride.pickup_longitude else None,
            destination_latitude=float(ride.destination_latitude) if ride.destination_latitude else None,
            destination_longitude=float(ride.destination_longitude) if ride.destination_longitude else None,
            pickup_at=ride.pickup_at,
            dropoff_at=ride.dropoff_at,
            actual_distance_miles=float(ride.actual_distance_miles) if ride.actual_distance_miles else None,
            actual_duration_minutes=ride.actual_duration_minutes,
            appointment_time=ride.appointment_time,
            mobility_level=ride.mobility_level,
            assistance_level=ride.assistance_level,
            cancellation_reason=ride.cancellation_reason,
            cancelled_at=ride.cancelled_at,
            rider_name=detail["rider_name"],
            rider_rating=detail["rider_rating"],
            rider_trip_count=detail["rider_trip_count"],
            driver_rating=RatingResponse.model_validate(detail["driver_rating"]) if detail["driver_rating"] else None,
            rider_rating_given=RatingResponse.model_validate(detail["rider_rating_given"]) if detail["rider_rating_given"] else None,
            timeline=[StatusLogResponse.model_validate(l) for l in detail["timeline"]],
        ),
    )


@router.get("/{ride_id}/timeline", response_model=StandardResponse[list[StatusLogResponse]])
async def get_ride_timeline(
    ride_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.DRIVER, UserRole.RIDER, UserRole.ADMIN, UserRole.FACILITY])),
    service: RideService = Depends(_get_ride_service),
):
    timeline = await service.get_ride_timeline(ride_id)
    return StandardResponse(
        data=[StatusLogResponse.model_validate(l) for l in timeline],
    )


@router.put("/{ride_id}/status", response_model=StandardResponse[RideResponse])
async def transition_ride_status(
    ride_id: UUID,
    request: StatusTransitionRequest,
    user: UserClaims = Depends(require_role([UserRole.DRIVER, UserRole.ADMIN])),
    service: RideService = Depends(_get_ride_service),
):
    ride = await service.transition_status(
        ride_id, request.status, user.id, request.notes
    )
    return StandardResponse(
        data=RideResponse.model_validate(ride),
        message=f"Ride status updated to {request.status}",
    )


@router.put("/{ride_id}/cancel", response_model=StandardResponse[RideResponse])
async def cancel_ride(
    ride_id: UUID,
    request: CancelRideRequest,
    user: UserClaims = Depends(require_role([UserRole.DRIVER, UserRole.RIDER, UserRole.ADMIN, UserRole.FACILITY])),
    service: RideService = Depends(_get_ride_service),
):
    ride = await service.cancel_ride(ride_id, user.id, request.reason)
    return StandardResponse(
        data=RideResponse.model_validate(ride),
        message="Ride cancelled",
    )
