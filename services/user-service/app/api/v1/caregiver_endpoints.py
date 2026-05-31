from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.ride_service_client import RideServiceClient
from app.config import settings
from app.dependencies import get_db, get_publisher
from app.repositories.caregiver_repo import CaregiverRepository
from app.repositories.fleet_repo import FleetRepository
from app.repositories.user_repo import UserRepository
from app.schemas.caregiver import (
    CaregiverCreate,
    CaregiverDetailResponse,
    CaregiverKPIs,
    CaregiverProfileCard,
    CaregiverRosterRow,
    CaregiverUpdate,
)
from app.services.caregiver_service import CaregiverService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import PaginatedResponse, StandardResponse

router = APIRouter()


def _get_service(
    session: AsyncSession = Depends(get_db),
    publisher: EventPublisher = Depends(get_publisher),
) -> CaregiverService:
    return CaregiverService(
        caregiver_repo=CaregiverRepository(session),
        user_repo=UserRepository(session),
        fleet_repo=FleetRepository(session),
        ride_client=RideServiceClient(settings.RIDE_SERVICE_URL),
        publisher=publisher,
    )


# --- Static routes first ---


@router.get(
    "/admin/caregivers/kpis",
    response_model=StandardResponse[CaregiverKPIs],
)
async def get_caregiver_kpis(
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: CaregiverService = Depends(_get_service),
):
    """Get caregiver KPI cards."""
    kpis = await service.get_kpis()
    return StandardResponse(data=kpis)


@router.get(
    "/admin/caregivers/profiles",
    response_model=PaginatedResponse[CaregiverProfileCard],
)
async def list_caregiver_profiles(
    specialty: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: CaregiverService = Depends(_get_service),
):
    """Get caregiver profile cards for Caregivers Profile tab."""
    cards, total = await service.get_caregiver_profiles(
        specialty=specialty, page=page, limit=limit
    )
    return PaginatedResponse(
        data=cards,
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.get(
    "/admin/caregivers",
    response_model=PaginatedResponse[CaregiverRosterRow],
)
async def list_caregivers(
    specialty: str | None = Query(None),
    status: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: CaregiverService = Depends(_get_service),
):
    """List all caregivers with filters for All Caregivers tab."""
    rows, total = await service.list_caregivers(
        specialty=specialty,
        status=status,
        search=search,
        page=page,
        limit=limit,
    )
    return PaginatedResponse(
        data=rows,
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.post(
    "/admin/caregivers",
    response_model=StandardResponse[dict],
    status_code=201,
)
async def create_caregiver(
    body: CaregiverCreate,
    admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: CaregiverService = Depends(_get_service),
):
    """Add a new caregiver (driver with specialty)."""
    try:
        result = await service.create_caregiver(
            first_name=body.first_name,
            last_name=body.last_name,
            email=body.email,
            phone=body.phone,
            specialty=body.specialty,
            city=body.city,
            province=body.province,
            capabilities=body.capabilities,
            fleet_id=body.fleet_id,
            admin_id=admin.id,
        )
        return StandardResponse(data=result, message="Caregiver created successfully")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Dynamic routes ---


@router.get(
    "/admin/caregivers/{caregiver_id}",
    response_model=StandardResponse[CaregiverDetailResponse],
)
async def get_caregiver_detail(
    caregiver_id: UUID,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: CaregiverService = Depends(_get_service),
):
    """Get detailed caregiver information with all tabs."""
    try:
        detail = await service.get_caregiver_detail(caregiver_id)
        return StandardResponse(data=detail)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put(
    "/admin/caregivers/{caregiver_id}",
    response_model=StandardResponse[dict],
)
async def update_caregiver(
    caregiver_id: UUID,
    body: CaregiverUpdate,
    admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: CaregiverService = Depends(_get_service),
):
    """Edit caregiver information."""
    try:
        result = await service.update_caregiver(
            caregiver_id=caregiver_id,
            first_name=body.first_name,
            last_name=body.last_name,
            email=body.email,
            phone=body.phone,
            specialty=body.specialty,
            city=body.city,
            province=body.province,
            capabilities=body.capabilities,
            fleet_id=body.fleet_id,
            admin_id=admin.id,
        )
        return StandardResponse(data=result, message="Caregiver updated successfully")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
