from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories.service_type_config_repo import ServiceTypeConfigRepository
from app.schemas.ride_type import (
    RideTypeCreate,
    RideTypeKPIs,
    RideTypeResponse,
    RideTypeUpdate,
)
from app.services.ride_type_service import RideTypeService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> RideTypeService:
    return RideTypeService(config_repo=ServiceTypeConfigRepository(session))


@router.get(
    "/admin/ride-types/kpis",
    response_model=StandardResponse[RideTypeKPIs],
)
async def get_ride_type_kpis(
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: RideTypeService = Depends(_get_service),
):
    """Get ride type KPI cards."""
    kpis = await service.get_kpis()
    return StandardResponse(data=kpis)


@router.get(
    "/admin/ride-types",
    response_model=StandardResponse[list[RideTypeResponse]],
)
async def list_ride_types(
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: RideTypeService = Depends(_get_service),
):
    """List all ride types/categories."""
    ride_types = await service.list_ride_types()
    return StandardResponse(data=ride_types)


@router.post(
    "/admin/ride-types",
    response_model=StandardResponse[RideTypeResponse],
    status_code=201,
)
async def create_ride_type(
    body: RideTypeCreate,
    admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: RideTypeService = Depends(_get_service),
):
    """Create a new ride type."""
    config = await service.create_ride_type(
        service_type=body.service_type,
        display_name=body.display_name,
        description=body.description,
        base_fare=body.base_fare,
        per_km_rate=body.per_km_rate,
        per_min_rate=body.per_min_rate,
        min_fare=body.min_fare,
        admin_id=admin.id,
    )

    return StandardResponse(
        data=RideTypeResponse(
            id=config.id,
            service_type=config.service_type,
            display_name=config.display_name,
            description=config.config.get("description"),
            base_fare=config.config["base_fare"],
            per_km_rate=config.config["per_km_rate"],
            per_min_rate=config.config["per_min_rate"],
            min_fare=config.config["min_fare"],
            is_active=config.is_active,
            created_at=config.created_at,
        ),
        message="Ride type created successfully",
    )


@router.get(
    "/admin/ride-types/{ride_type_id}",
    response_model=StandardResponse[RideTypeResponse],
)
async def get_ride_type(
    ride_type_id: UUID,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: RideTypeService = Depends(_get_service),
):
    """Get ride type details."""
    try:
        config = await service.get_ride_type(ride_type_id)
        return StandardResponse(
            data=RideTypeResponse(
                id=config.id,
                service_type=config.service_type,
                display_name=config.display_name,
                description=config.config.get("description"),
                base_fare=config.config["base_fare"],
                per_km_rate=config.config["per_km_rate"],
                per_min_rate=config.config["per_min_rate"],
                min_fare=config.config["min_fare"],
                is_active=config.is_active,
                created_at=config.created_at,
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put(
    "/admin/ride-types/{ride_type_id}",
    response_model=StandardResponse[RideTypeResponse],
)
async def update_ride_type(
    ride_type_id: UUID,
    body: RideTypeUpdate,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: RideTypeService = Depends(_get_service),
):
    """Update ride type configuration."""
    try:
        config = await service.update_ride_type(
            ride_type_id=ride_type_id,
            display_name=body.display_name,
            description=body.description,
            base_fare=body.base_fare,
            per_km_rate=body.per_km_rate,
            per_min_rate=body.per_min_rate,
            min_fare=body.min_fare,
            is_active=body.is_active,
        )

        return StandardResponse(
            data=RideTypeResponse(
                id=config.id,
                service_type=config.service_type,
                display_name=config.display_name,
                description=config.config.get("description"),
                base_fare=config.config["base_fare"],
                per_km_rate=config.config["per_km_rate"],
                per_min_rate=config.config["per_min_rate"],
                min_fare=config.config["min_fare"],
                is_active=config.is_active,
                created_at=config.created_at,
            ),
            message="Ride type updated successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put(
    "/admin/ride-types/{ride_type_id}/toggle",
    response_model=StandardResponse[RideTypeResponse],
)
async def toggle_ride_type(
    ride_type_id: UUID,
    is_active: bool,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: RideTypeService = Depends(_get_service),
):
    """Toggle ride type active/inactive."""
    try:
        config = await service.toggle_ride_type(ride_type_id, is_active)

        return StandardResponse(
            data=RideTypeResponse(
                id=config.id,
                service_type=config.service_type,
                display_name=config.display_name,
                description=config.config.get("description"),
                base_fare=config.config["base_fare"],
                per_km_rate=config.config["per_km_rate"],
                per_min_rate=config.config["per_min_rate"],
                min_fare=config.config["min_fare"],
                is_active=config.is_active,
                created_at=config.created_at,
            ),
            message=f"Ride type {'activated' if is_active else 'deactivated'}",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete(
    "/admin/ride-types/{ride_type_id}",
    response_model=StandardResponse,
)
async def delete_ride_type(
    ride_type_id: UUID,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: RideTypeService = Depends(_get_service),
):
    """Delete a ride type."""
    try:
        await service.delete_ride_type(ride_type_id)
        return StandardResponse(message="Ride type deleted successfully")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
