from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_publisher
from app.repositories.driver_repo import DriverRepository
from app.schemas.driver import (
    DriverProfileResponse,
    DriverStatusRequest,
    UpdateDriverProfileRequest,
)
from app.services.driver_service import DriverService
from mediride_common.auth.dependencies import get_current_user, require_role
from mediride_common.auth.models import UserClaims
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import PaginatedResponse, StandardResponse

router = APIRouter(prefix="/drivers")


def _get_driver_service(
    session: AsyncSession = Depends(get_db),
    publisher: EventPublisher = Depends(get_publisher),
) -> DriverService:
    return DriverService(DriverRepository(session), publisher)


@router.get("/me", response_model=StandardResponse[DriverProfileResponse])
async def get_my_driver_profile(
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: DriverService = Depends(_get_driver_service),
):
    driver = await service.get_driver_profile(user.id)
    return StandardResponse(data=DriverProfileResponse.model_validate(driver))


@router.put("/me", response_model=StandardResponse[DriverProfileResponse])
async def update_my_driver_profile(
    request: UpdateDriverProfileRequest,
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: DriverService = Depends(_get_driver_service),
):
    update_data = request.model_dump(exclude_unset=True)
    driver = await service.update_driver_profile(user.id, **update_data)
    return StandardResponse(
        data=DriverProfileResponse.model_validate(driver),
        message="Driver profile updated",
    )


@router.put("/me/status", response_model=StandardResponse[DriverProfileResponse])
async def toggle_online_status(
    request: DriverStatusRequest,
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: DriverService = Depends(_get_driver_service),
):
    driver = await service.set_online_status(user.id, request.is_online)
    status = "online" if request.is_online else "offline"
    return StandardResponse(
        data=DriverProfileResponse.model_validate(driver),
        message=f"Driver is now {status}",
    )


@router.get("", response_model=PaginatedResponse[DriverProfileResponse])
async def list_drivers(
    business_id: UUID | None = None,
    is_online: bool | None = None,
    is_approved: bool | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(
        require_role([UserRole.ADMIN, UserRole.BUSINESS])
    ),
    service: DriverService = Depends(_get_driver_service),
):
    # Business users can only see their own drivers
    if user.role == UserRole.BUSINESS:
        business_id = user.business_id

    if not business_id:
        from mediride_common.exceptions import ValidationError
        raise ValidationError("business_id is required")

    offset = (page - 1) * limit
    drivers, total = await service.list_drivers(
        business_id, offset, limit, is_online, is_approved
    )
    return PaginatedResponse(
        data=[DriverProfileResponse.model_validate(d) for d in drivers],
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit,
    )


@router.put("/{driver_id}/approve", response_model=StandardResponse[DriverProfileResponse])
async def approve_driver(
    driver_id: UUID,
    user: UserClaims = Depends(
        require_role([UserRole.ADMIN, UserRole.BUSINESS])
    ),
    service: DriverService = Depends(_get_driver_service),
):
    driver = await service.approve_driver(driver_id)
    return StandardResponse(
        data=DriverProfileResponse.model_validate(driver),
        message="Driver approved",
    )


@router.put("/{driver_id}/suspend", response_model=StandardResponse[DriverProfileResponse])
async def suspend_driver(
    driver_id: UUID,
    user: UserClaims = Depends(
        require_role([UserRole.ADMIN, UserRole.BUSINESS])
    ),
    service: DriverService = Depends(_get_driver_service),
):
    driver = await service.suspend_driver(driver_id)
    return StandardResponse(
        data=DriverProfileResponse.model_validate(driver),
        message="Driver suspended",
    )
