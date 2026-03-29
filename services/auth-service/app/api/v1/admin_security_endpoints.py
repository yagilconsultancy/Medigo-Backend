from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.security_settings import (
    SecurityKPIs,
    SecuritySettingsResponse,
    UpdateSecuritySettingsRequest,
)
from app.services.security_settings_service import SecuritySettingsService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> SecuritySettingsService:
    return SecuritySettingsService(session)


@router.get("/security/kpis", response_model=StandardResponse[SecurityKPIs])
async def get_security_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: SecuritySettingsService = Depends(_get_service),
):
    data = await service.get_kpis()
    return StandardResponse(data=SecurityKPIs(**data))


@router.get("/security/settings", response_model=StandardResponse[SecuritySettingsResponse])
async def get_security_settings(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: SecuritySettingsService = Depends(_get_service),
):
    data = await service.get_settings()
    return StandardResponse(data=SecuritySettingsResponse(**data))


@router.put("/security/settings", response_model=StandardResponse[SecuritySettingsResponse])
async def update_security_settings(
    body: UpdateSecuritySettingsRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: SecuritySettingsService = Depends(_get_service),
):
    update_data = body.model_dump(exclude_unset=True)
    data = await service.update_settings(user.id, **update_data)
    return StandardResponse(data=SecuritySettingsResponse(**data), message="Security settings updated")
