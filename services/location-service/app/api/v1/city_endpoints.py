from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories.city_repo import CityRepository
from app.schemas.city import (
    CityCreate,
    CityKPIs,
    CityResponse,
    CityRow,
    CityUpdate,
)
from app.services.city_service import CityService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> CityService:
    return CityService(city_repo=CityRepository(session))


@router.get(
    "/admin/cities/kpis",
    response_model=StandardResponse[CityKPIs],
)
async def get_city_kpis(
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: CityService = Depends(_get_service),
):
    """Get city KPI cards."""
    kpis = await service.get_kpis()
    return StandardResponse(data=kpis)


@router.get(
    "/admin/cities",
    response_model=StandardResponse[list[CityRow]],
)
async def list_cities(
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: CityService = Depends(_get_service),
):
    """List all operating cities with stats."""
    cities = await service.list_cities()
    return StandardResponse(data=cities)


@router.post(
    "/admin/cities",
    response_model=StandardResponse[CityResponse],
    status_code=201,
)
async def create_city(
    body: CityCreate,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: CityService = Depends(_get_service),
):
    """Add a new operating city."""
    city = await service.create_city(
        name=body.name,
        province=body.province,
        number_of_zones=body.number_of_zones,
    )
    return StandardResponse(
        data=CityResponse.model_validate(city), message="City created successfully"
    )


@router.get(
    "/admin/cities/{city_id}",
    response_model=StandardResponse[CityResponse],
)
async def get_city(
    city_id: UUID,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: CityService = Depends(_get_service),
):
    """Get city details."""
    try:
        city = await service.get_city(city_id)
        return StandardResponse(data=CityResponse.model_validate(city))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put(
    "/admin/cities/{city_id}",
    response_model=StandardResponse[CityResponse],
)
async def update_city(
    city_id: UUID,
    body: CityUpdate,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: CityService = Depends(_get_service),
):
    """Update city information."""
    try:
        city = await service.update_city(
            city_id=city_id,
            name=body.name,
            province=body.province,
            number_of_zones=body.number_of_zones,
            is_active=body.is_active,
        )
        return StandardResponse(
            data=CityResponse.model_validate(city), message="City updated successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put(
    "/admin/cities/{city_id}/toggle",
    response_model=StandardResponse[CityResponse],
)
async def toggle_city_status(
    city_id: UUID,
    is_active: bool,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: CityService = Depends(_get_service),
):
    """Toggle city active/inactive status."""
    try:
        city = await service.toggle_city_status(city_id, is_active)
        return StandardResponse(
            data=CityResponse.model_validate(city),
            message=f"City {'activated' if is_active else 'deactivated'}",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete(
    "/admin/cities/{city_id}",
    response_model=StandardResponse,
)
async def delete_city(
    city_id: UUID,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: CityService = Depends(_get_service),
):
    """Delete a city."""
    try:
        await service.delete_city(city_id)
        return StandardResponse(message="City deleted successfully")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
