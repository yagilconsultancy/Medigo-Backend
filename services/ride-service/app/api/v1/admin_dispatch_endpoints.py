"""Admin dispatch center endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.user_service_client import UserServiceClient
from app.config import settings
from app.dependencies import get_db, get_publisher, module_access_checker
from app.repositories.dispatch_repo import DispatchRepository
from app.schemas.dispatch import (
    AutoDispatchSettings,
    AvailableDriverItem,
    DispatchDashboardResponse,
    ManualAssignmentRequest,
    TriggerAutoDispatchResponse,
    UpdateAutoDispatchSettingsRequest,
)
from app.services.dispatch_service import DispatchService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter(prefix="/admin/dispatch")


def _get_service(
    session: AsyncSession = Depends(get_db),
    publisher: EventPublisher = Depends(get_publisher),
) -> DispatchService:
    user_client = UserServiceClient(settings.USER_SERVICE_URL)
    return DispatchService(
        repo=DispatchRepository(session),
        user_service_client=user_client,
        publisher=publisher,
    )


# --- Dispatch Center Dashboard ---


@router.get("/dashboard", response_model=StandardResponse[DispatchDashboardResponse])
async def get_dispatch_dashboard(
    _admin: UserClaims = Depends(module_access_checker.require_module_access("dispatch_center")),
    service: DispatchService = Depends(_get_service),
):
    """
    Get dispatch center dashboard with KPIs, unassigned rides, and available drivers.
    Supports the main dispatch center view.
    Requires: dispatch_center module access
    """
    result = await service.get_dispatch_dashboard()
    return StandardResponse(data=result)


@router.get("/active-trips", response_model=StandardResponse[list[dict]])
async def get_active_trips(
    _admin: UserClaims = Depends(module_access_checker.require_module_access("dispatch_center")),
    service: DispatchService = Depends(_get_service),
):
    """
    Get all active trips for live dispatch map.
    Returns trips with driver_arrived or in_progress status.
    Use Socket.IO /tracking namespace to get real-time location updates.
    Requires: dispatch_center module access
    """
    trips = await service.get_active_trips()
    return StandardResponse(data=trips)


# --- Unassigned Rides ---


@router.get("/unassigned-rides", response_model=StandardResponse)
async def get_unassigned_rides(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    _admin: UserClaims = Depends(module_access_checker.require_module_access("dispatch_center")),
    service: DispatchService = Depends(_get_service),
):
    """
    Get paginated list of rides that need driver assignment.
    Filtered for approved rides with no driver assigned.
    Requires: dispatch_center module access
    """
    result = await service.get_unassigned_rides(page=page, limit=limit)
    return StandardResponse(data=result)


# --- Available Drivers ---


@router.get(
    "/available-drivers", response_model=StandardResponse[list[AvailableDriverItem]]
)
async def get_available_drivers(
    _admin: UserClaims = Depends(module_access_checker.require_module_access("dispatch_center")),
    service: DispatchService = Depends(_get_service),
):
    """
    Get list of drivers available for assignment.
    Filters for active, online, and approved drivers.
    Requires: dispatch_center module access
    """
    drivers = await service.get_available_drivers()
    return StandardResponse(data=drivers)


# --- Manual Assignment ---


@router.post("/rides/{ride_id}/assign", response_model=StandardResponse)
async def manually_assign_driver(
    ride_id: UUID,
    request: ManualAssignmentRequest,
    admin: UserClaims = Depends(module_access_checker.require_module_access("dispatch_center")),
    service: DispatchService = Depends(_get_service),
):
    """
    Manually assign a driver to a ride from the dispatch center.
    Updates ride status to 'driver_assigned' and publishes event.
    Requires: dispatch_center module access
    """
    # Get driver details to fetch business_id
    driver_profile = await service.user_client.get_driver_profile(request.driver_id)
    business_id = None
    if driver_profile and driver_profile.get("business_id"):
        business_id = UUID(driver_profile["business_id"])

    # Assign driver
    ride = await service.repo.assign_driver_to_ride(
        ride_id, request.driver_id, business_id
    )

    if not ride:
        return StandardResponse(
            success=False, message="Ride not found", data=None
        )

    # Publish event
    await service.publisher.publish(
        Exchanges.RIDES,
        RoutingKeys.RIDE_DRIVER_ASSIGNED,
        {
            "ride_id": str(ride_id),
            "driver_id": str(request.driver_id),
            "business_id": str(business_id) if business_id else None,
            "assigned_by": str(admin.id),
            "assigned_via": "manual_dispatch",
        },
    )

    return StandardResponse(
        data={"ride_id": str(ride_id), "driver_id": str(request.driver_id)},
        message="Driver assigned successfully",
    )


# --- Auto-Dispatch Settings ---


@router.get("/settings", response_model=StandardResponse[AutoDispatchSettings])
async def get_dispatch_settings(
    _admin: UserClaims = Depends(module_access_checker.require_module_access("dispatch_center")),
    service: DispatchService = Depends(_get_service),
):
    """
    Get current auto-dispatch settings configuration.
    Includes distance matching logic, priority rules, and fallback behavior.
    Requires: dispatch_center module access
    """
    settings = await service.get_dispatch_settings()
    return StandardResponse(data=settings)


@router.put("/settings", response_model=StandardResponse[AutoDispatchSettings])
async def update_dispatch_settings(
    request: UpdateAutoDispatchSettingsRequest,
    admin: UserClaims = Depends(module_access_checker.require_module_access("dispatch_center")),
    service: DispatchService = Depends(_get_service),
):
    """
    Update auto-dispatch settings.
    Allows enabling/disabling auto-dispatch and configuring matching rules.
    Requires: dispatch_center module access
    """
    settings = await service.update_dispatch_settings(admin.id, request)
    return StandardResponse(data=settings, message="Settings updated successfully")


# --- Auto-Dispatch Trigger ---


@router.post("/auto-assign", response_model=StandardResponse[TriggerAutoDispatchResponse])
async def trigger_auto_dispatch(
    admin: UserClaims = Depends(module_access_checker.require_module_access("dispatch_center")),
    service: DispatchService = Depends(_get_service),
):
    """
    Manually trigger auto-dispatch for all eligible rides.
    Processes unassigned rides scheduled within the next 24 hours.
    Returns assignment results for each ride.
    Requires: dispatch_center module access
    """
    result = await service.trigger_auto_dispatch(admin.id)
    return StandardResponse(
        data=result,
        message=f"Auto-dispatch completed: {result.assigned_count} assigned, {result.failed_count} failed",
    )
