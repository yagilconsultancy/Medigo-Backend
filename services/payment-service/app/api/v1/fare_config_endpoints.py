from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.fare_config import (
    CommissionViewResponse,
    RoutePricingResponse,
    RoutePricingUpdate,
    ServiceTypeConfigResponse,
    ServiceTypeConfigUpdate,
    ServiceTypeListResponse,
)
from app.services.fare_config_service import FareConfigService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> FareConfigService:
    return FareConfigService(session)


@router.get("/fare-config/service-types", response_model=StandardResponse[ServiceTypeListResponse])
async def list_service_types(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FareConfigService = Depends(_get_service),
):
    types = await service.get_service_types()
    return StandardResponse(data=ServiceTypeListResponse(service_types=types))


@router.get("/fare-config/{service_type}", response_model=StandardResponse[ServiceTypeConfigResponse])
async def get_service_type_config(
    service_type: str,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FareConfigService = Depends(_get_service),
):
    data = await service.get_config(service_type)
    if not data:
        raise HTTPException(status_code=404, detail="Service type not found")
    return StandardResponse(data=ServiceTypeConfigResponse(**data))


@router.put("/fare-config/{service_type}", response_model=StandardResponse[ServiceTypeConfigResponse])
async def update_service_type_config(
    service_type: str,
    body: ServiceTypeConfigUpdate,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FareConfigService = Depends(_get_service),
):
    data = await service.update_config(
        service_type, body.config, admin_id=user.id, admin_name=user.email or "Admin"
    )
    if not data:
        raise HTTPException(status_code=404, detail="Service type not found")
    return StandardResponse(data=ServiceTypeConfigResponse(**data))


@router.get("/fare-config/{service_type}/routes", response_model=StandardResponse[RoutePricingResponse])
async def get_route_pricing(
    service_type: str,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FareConfigService = Depends(_get_service),
):
    data = await service.get_routes(service_type)
    if not data:
        raise HTTPException(status_code=404, detail="Service type not found")
    return StandardResponse(data=RoutePricingResponse(**data))


@router.put("/fare-config/{service_type}/routes", response_model=StandardResponse[RoutePricingResponse])
async def update_route_pricing(
    service_type: str,
    body: RoutePricingUpdate,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FareConfigService = Depends(_get_service),
):
    data = await service.update_routes(
        service_type, body.routes, admin_id=user.id, admin_name=user.email or "Admin"
    )
    if not data:
        raise HTTPException(status_code=404, detail="Service type not found")
    return StandardResponse(data=RoutePricingResponse(**data))


@router.get("/fare-config/{service_type}/commission", response_model=StandardResponse[CommissionViewResponse])
async def get_commission_view(
    service_type: str,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: FareConfigService = Depends(_get_service),
):
    data = await service.get_commission_view(service_type)
    if not data:
        raise HTTPException(status_code=404, detail="Service type not found")
    return StandardResponse(data=CommissionViewResponse(**data))
