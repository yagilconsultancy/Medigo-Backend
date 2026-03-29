from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.commission import (
    CommissionConfigResponse,
    CommissionConfigUpdate,
    CommissionKPIs,
)
from app.services.commission_service import CommissionService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> CommissionService:
    return CommissionService(session)


@router.get("/commission/kpis", response_model=StandardResponse[CommissionKPIs])
async def get_commission_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: CommissionService = Depends(_get_service),
):
    data = await service.get_kpis()
    return StandardResponse(data=CommissionKPIs(**data))


@router.get("/commission", response_model=StandardResponse[CommissionConfigResponse])
async def get_commission_config(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: CommissionService = Depends(_get_service),
):
    data = await service.get_config()
    if not data:
        raise HTTPException(status_code=404, detail="No active commission config")
    return StandardResponse(data=CommissionConfigResponse(**data))


@router.put("/commission", response_model=StandardResponse[CommissionConfigResponse])
async def update_commission_config(
    body: CommissionConfigUpdate,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: CommissionService = Depends(_get_service),
):
    data = await service.update_config(
        body.model_dump(),
        admin_id=user.id,
        admin_name=user.email or "Admin",
    )
    return StandardResponse(data=CommissionConfigResponse(**data))
