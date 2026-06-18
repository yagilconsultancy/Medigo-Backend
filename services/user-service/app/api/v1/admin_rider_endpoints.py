from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.auth_service_client import AuthServiceClient
from app.clients.payment_service_client import PaymentServiceClient
from app.clients.ride_service_client import RideServiceClient
from app.config import settings
from app.dependencies import get_db, get_publisher
from app.repositories.admin_rider_repo import AdminRiderRepository
from app.repositories.rider_issue_repo import RiderIssueRepository
from app.schemas.admin_rider import (
    AddIssueNoteRequest,
    AdminRiderActivityResponse,
    AdminRiderDetailResponse,
    AdminRiderListResponse,
    AdminRiderProfileCard,
    CreateRiderIssueRequest,
    RiderIssueDetailResponse,
    RiderIssueListResponse,
    SuspendRiderRequest,
    UpdateIssueStatusRequest,
)
from app.services.admin_rider_service import AdminRiderService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import PaginatedResponse, StandardResponse

router = APIRouter(prefix="/admin/riders")


def _get_service(
    session: AsyncSession = Depends(get_db),
    publisher: EventPublisher = Depends(get_publisher),
) -> AdminRiderService:
    return AdminRiderService(
        repo=AdminRiderRepository(session),
        issue_repo=RiderIssueRepository(session),
        ride_client=RideServiceClient(settings.RIDE_SERVICE_URL),
        payment_client=PaymentServiceClient(settings.PAYMENT_SERVICE_URL),
        auth_client=AuthServiceClient(settings.AUTH_SERVICE_URL),
        publisher=publisher,
    )


# --- Static routes first (before /{rider_id}) ---


@router.get("/profiles", response_model=PaginatedResponse[AdminRiderProfileCard])
async def get_rider_profiles(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRiderService = Depends(_get_service),
):
    """Rider profile cards with insurance, emergency contact, payment method."""
    profiles, total = await service.get_rider_profiles(search=search, page=page, limit=limit)
    return PaginatedResponse(
        data=profiles,
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.get("/activity", response_model=StandardResponse[AdminRiderActivityResponse])
async def get_rider_activity(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRiderService = Depends(_get_service),
):
    """Rider activity overview with frequency, trend, and KPIs."""
    result = await service.get_rider_activity(page=page, limit=limit)
    return StandardResponse(data=result)


@router.get("/issues", response_model=StandardResponse[RiderIssueListResponse])
async def list_rider_issues(
    status: str | None = Query(None),
    priority: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRiderService = Depends(_get_service),
):
    """Rider issues list with KPIs and status/priority filters."""
    result = await service.list_issues(
        status=status, priority=priority, search=search, page=page, limit=limit
    )
    return StandardResponse(data=result)


@router.post(
    "/issues",
    response_model=StandardResponse[RiderIssueDetailResponse],
    status_code=201,
)
async def create_rider_issue(
    body: CreateRiderIssueRequest,
    admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRiderService = Depends(_get_service),
):
    """Create a new rider issue."""
    try:
        result = await service.create_issue(admin.id, body)
        return StandardResponse(data=result, message="Issue created")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/issues/{issue_id}",
    response_model=StandardResponse[RiderIssueDetailResponse],
)
async def get_rider_issue_detail(
    issue_id: UUID,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRiderService = Depends(_get_service),
):
    """Get rider issue detail with activity log."""
    try:
        result = await service.get_issue_detail(issue_id)
        return StandardResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put(
    "/issues/{issue_id}/status",
    response_model=StandardResponse[RiderIssueDetailResponse],
)
async def update_rider_issue_status(
    issue_id: UUID,
    body: UpdateIssueStatusRequest,
    admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRiderService = Depends(_get_service),
):
    """Update rider issue status (open/under_review/resolved)."""
    try:
        result = await service.update_issue_status(issue_id, body.status, admin.id)
        return StandardResponse(data=result, message=f"Issue status updated to {body.status}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/issues/{issue_id}/notes",
    response_model=StandardResponse[RiderIssueDetailResponse],
    status_code=201,
)
async def add_rider_issue_note(
    issue_id: UUID,
    body: AddIssueNoteRequest,
    admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRiderService = Depends(_get_service),
):
    """Add a note to a rider issue."""
    try:
        result = await service.add_issue_note(issue_id, admin.id, body)
        return StandardResponse(data=result, message="Note added")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- List + Dynamic routes ---


@router.get("", response_model=StandardResponse[AdminRiderListResponse])
async def list_riders(
    search: str | None = Query(None),
    status: str | None = Query(None),
    sort_by: str = Query("created_at", pattern="^(created_at|name)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRiderService = Depends(_get_service),
):
    """List all riders with KPIs, search, status filter, and pagination."""
    result = await service.list_riders(
        search=search, status=status, sort_by=sort_by, page=page, limit=limit
    )
    return StandardResponse(data=result)


@router.get("/{rider_id}", response_model=StandardResponse[AdminRiderDetailResponse])
async def get_rider_detail(
    rider_id: UUID,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRiderService = Depends(_get_service),
):
    """Get full rider detail with trip stats, payment methods, emergency contacts."""
    try:
        result = await service.get_rider_detail(rider_id)
        return StandardResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put(
    "/{rider_id}/suspend",
    response_model=StandardResponse[AdminRiderDetailResponse],
)
async def suspend_rider(
    rider_id: UUID,
    body: SuspendRiderRequest,
    admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRiderService = Depends(_get_service),
):
    """Suspend a rider with a reason."""
    try:
        result = await service.suspend_rider(rider_id, body.reason, admin.id)
        return StandardResponse(data=result, message="Rider suspended")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/{rider_id}/reinstate",
    response_model=StandardResponse[AdminRiderDetailResponse],
)
async def reinstate_rider(
    rider_id: UUID,
    admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRiderService = Depends(_get_service),
):
    """Reinstate a suspended rider."""
    try:
        result = await service.reinstate_rider(rider_id, admin.id)
        return StandardResponse(data=result, message="Rider reinstated")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{rider_id}/rides", response_model=StandardResponse)
async def get_rider_rides(
    rider_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRiderService = Depends(_get_service),
):
    """Get a rider's ride history from ride-service."""
    result = await service.get_rider_rides(rider_id, page=page, limit=limit)
    return StandardResponse(data=result)
