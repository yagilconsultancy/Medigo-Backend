from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.payment_service_client import PaymentServiceClient
from app.clients.user_service_client import UserServiceClient
from app.config import settings
from app.dependencies import get_db, get_publisher
from app.repositories.admin_booking_repo import AdminBookingRepository
from app.repositories.admin_note_repo import AdminNoteRepository
from app.repositories.rating_repo import RatingRepository
from app.repositories.recurring_ride_repo import RecurringRideRepository
from app.repositories.ride_repo import RideRepository
from app.repositories.ride_request_repo import RideRequestRepository
from app.repositories.status_log_repo import StatusLogRepository
from app.schemas.admin_booking import (
    AdminBookingDetailResponse,
    AdminNoteResponse,
    ApproveBookingRequest,
    AssignCaregiverRequest,
    AssignDriverRequest,
    AvailableDriverResponse,
    CancelledTripResponse,
    CancelledTripsKPIs,
    CancelTripRequest,
    CreateAdminNoteRequest,
    DeclineBookingRequest,
    PendingBookingResponse,
    PendingBookingsKPIs,
    ReassignDriverRequest,
    ScheduledTripResponse,
    ScheduledTripsKPIs,
)
from app.schemas.ride import RideResponse
from app.services.admin_booking_service import AdminBookingService
from app.services.ride_service import RideService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import PaginatedResponse, StandardResponse

router = APIRouter()


def _get_service(
    session: AsyncSession = Depends(get_db),
    publisher: EventPublisher = Depends(get_publisher),
) -> AdminBookingService:
    user_client = UserServiceClient(settings.USER_SERVICE_URL)
    ride_service = RideService(
        ride_repo=RideRepository(session),
        request_repo=RideRequestRepository(session),
        status_log_repo=StatusLogRepository(session),
        rating_repo=RatingRepository(session),
        recurring_ride_repo=RecurringRideRepository(session),
        publisher=publisher,
        user_client=user_client,
    )
    return AdminBookingService(
        booking_repo=AdminBookingRepository(session),
        note_repo=AdminNoteRepository(session),
        ride_repo=RideRepository(session),
        status_log_repo=StatusLogRepository(session),
        ride_service=ride_service,
        user_client=user_client,
        payment_client=PaymentServiceClient(settings.PAYMENT_SERVICE_URL),
    )


# =====================================================================
# STATIC PATHS FIRST (must come before /{ride_id} dynamic paths)
# =====================================================================

# ---- All Bookings ----

@router.get("/bookings", response_model=PaginatedResponse[RideResponse])
async def get_all_bookings(
    status: str | None = Query(
        default=None,
        description=(
            "Filter by status. Supports single value, comma-separated multiple values, or grouped aliases. "
            "Grouped aliases: pending|approved|declined. "
            "Individual statuses: requested|pending_business_assignment|confirmed|driver_assigned|"
            "driver_en_route|driver_arrived|in_progress|completed|cancelled|no_show. "
            "Examples: ?status=requested or ?status=requested,confirmed,driver_assigned or ?status=pending,approved"
        ),
    ),
    ride_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBookingService = Depends(_get_service),
):
    """All bookings with status tabs, ride type filter, and search."""
    offset = (page - 1) * limit
    rides, total = await service.get_all_bookings(
        status_filter=status,
        ride_type_filter=ride_type,
        search=search,
        offset=offset,
        limit=limit,
    )
    return PaginatedResponse(
        data=[RideResponse.model_validate(r) for r in rides],
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


# ---- Pending Bookings ----

@router.get("/bookings/pending", response_model=PaginatedResponse[PendingBookingResponse])
async def get_pending_bookings(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBookingService = Depends(_get_service),
):
    """Pending ride requests awaiting admin action."""
    offset = (page - 1) * limit
    bookings, total = await service.get_pending_bookings(offset, limit)
    return PaginatedResponse(
        data=bookings,
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.get("/bookings/pending/kpis", response_model=StandardResponse[PendingBookingsKPIs])
async def get_pending_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBookingService = Depends(_get_service),
):
    """KPI cards for pending bookings view."""
    kpis = await service.get_pending_kpis()
    return StandardResponse(data=kpis)


# ---- Scheduled Trips ----

@router.get("/bookings/scheduled", response_model=PaginatedResponse[ScheduledTripResponse])
async def get_scheduled_trips(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBookingService = Depends(_get_service),
):
    """Future and recurring bookings scheduled in advance."""
    offset = (page - 1) * limit
    trips, total = await service.get_scheduled_trips(offset, limit)
    return PaginatedResponse(
        data=trips,
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.get("/bookings/scheduled/kpis", response_model=StandardResponse[ScheduledTripsKPIs])
async def get_scheduled_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBookingService = Depends(_get_service),
):
    """KPI cards for scheduled trips view."""
    kpis = await service.get_scheduled_kpis()
    return StandardResponse(data=kpis)


# ---- Cancelled Trips ----

@router.get("/bookings/cancelled", response_model=PaginatedResponse[CancelledTripResponse])
async def get_cancelled_trips(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBookingService = Depends(_get_service),
):
    """Cancelled ride history and cancellation reasons."""
    offset = (page - 1) * limit
    trips, total = await service.get_cancelled_trips(offset, limit)
    return PaginatedResponse(
        data=trips,
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.get("/bookings/cancelled/kpis", response_model=StandardResponse[CancelledTripsKPIs])
async def get_cancelled_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBookingService = Depends(_get_service),
):
    """KPI cards for cancelled trips view."""
    kpis = await service.get_cancelled_kpis()
    return StandardResponse(data=kpis)


# =====================================================================
# DYNAMIC PATHS (/{ride_id}) — must come AFTER static paths
# =====================================================================

@router.get("/bookings/{ride_id}", response_model=StandardResponse[AdminBookingDetailResponse])
async def get_booking_detail(
    ride_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBookingService = Depends(_get_service),
):
    """Full booking detail with admin notes, timeline, fare breakdown."""
    detail = await service.get_booking_detail(ride_id)
    return StandardResponse(data=detail)


@router.put("/bookings/{ride_id}/approve", response_model=StandardResponse[RideResponse])
async def approve_booking(
    ride_id: UUID,
    body: ApproveBookingRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBookingService = Depends(_get_service),
    session: AsyncSession = Depends(get_db),
):
    """Approve a booking (REQUESTED -> CONFIRMED)."""
    ride = await service.approve_booking(ride_id, user.id, body.notes)
    await session.commit()
    return StandardResponse(
        data=RideResponse.model_validate(ride),
        message="Booking approved",
    )


@router.put("/bookings/{ride_id}/decline", response_model=StandardResponse[RideResponse])
async def decline_booking(
    ride_id: UUID,
    body: DeclineBookingRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBookingService = Depends(_get_service),
    session: AsyncSession = Depends(get_db),
):
    """Decline a booking (REQUESTED -> CANCELLED)."""
    ride = await service.decline_booking(ride_id, user.id, body.reason)
    await session.commit()
    return StandardResponse(
        data=RideResponse.model_validate(ride),
        message="Booking declined",
    )


@router.put("/bookings/{ride_id}/assign-driver", response_model=StandardResponse[RideResponse])
async def assign_driver(
    ride_id: UUID,
    body: AssignDriverRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBookingService = Depends(_get_service),
    session: AsyncSession = Depends(get_db),
):
    """Assign a driver to a booking."""
    ride = await service.assign_driver(ride_id, body.driver_id, user.id)
    await session.commit()
    return StandardResponse(
        data=RideResponse.model_validate(ride),
        message="Driver assigned",
    )


@router.put("/bookings/{ride_id}/reassign-driver", response_model=StandardResponse[RideResponse])
async def reassign_driver(
    ride_id: UUID,
    body: ReassignDriverRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBookingService = Depends(_get_service),
    session: AsyncSession = Depends(get_db),
):
    """Reassign a driver on an active ride."""
    ride = await service.reassign_driver(ride_id, body.driver_id, user.id, body.reason)
    await session.commit()
    return StandardResponse(
        data=RideResponse.model_validate(ride),
        message="Driver reassigned",
    )


@router.put("/bookings/{ride_id}/assign-caregiver", response_model=StandardResponse[RideResponse])
async def assign_caregiver(
    ride_id: UUID,
    body: AssignCaregiverRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBookingService = Depends(_get_service),
    session: AsyncSession = Depends(get_db),
):
    """
    Assign a caregiver (care assistant) to a booking.

    Only permitted for scheduled (future) `TRANSPORT_CARE_ASSISTANT` rides
    in REQUESTED or CONFIRMED status. The selected user must have a
    caregiver specialty set on their driver profile.
    """
    ride = await service.assign_caregiver(ride_id, body.caregiver_id, user.id)
    await session.commit()
    return StandardResponse(
        data=RideResponse.model_validate(ride),
        message="Caregiver assigned",
    )


@router.get(
    "/bookings/{ride_id}/available-drivers",
    response_model=StandardResponse[list[AvailableDriverResponse]],
)
async def get_available_drivers(
    ride_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBookingService = Depends(_get_service),
):
    """List available drivers for assignment to this booking."""
    drivers = await service.get_available_drivers(ride_id)
    return StandardResponse(data=drivers)


@router.put("/bookings/{ride_id}/cancel", response_model=StandardResponse[RideResponse])
async def cancel_trip(
    ride_id: UUID,
    body: CancelTripRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBookingService = Depends(_get_service),
    session: AsyncSession = Depends(get_db),
):
    """Admin cancel a trip."""
    ride = await service.cancel_trip(ride_id, user.id, body.reason)
    await session.commit()
    return StandardResponse(
        data=RideResponse.model_validate(ride),
        message="Trip cancelled",
    )


# ---- Admin Notes ----

@router.get(
    "/bookings/{ride_id}/notes",
    response_model=StandardResponse[list[AdminNoteResponse]],
)
async def get_booking_notes(
    ride_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBookingService = Depends(_get_service),
):
    """Get all admin notes for a booking."""
    notes = await service.get_notes(ride_id)
    return StandardResponse(data=notes)


@router.post(
    "/bookings/{ride_id}/notes",
    response_model=StandardResponse[AdminNoteResponse],
)
async def add_booking_note(
    ride_id: UUID,
    body: CreateAdminNoteRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBookingService = Depends(_get_service),
    session: AsyncSession = Depends(get_db),
):
    """Add an admin note to a booking."""
    note = await service.add_note(ride_id, user.id, body.content, body.author_type)
    await session.commit()
    return StandardResponse(data=note, message="Note added")
