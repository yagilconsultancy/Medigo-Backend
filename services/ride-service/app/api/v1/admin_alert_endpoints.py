from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.safety_alert import AlertKPIs, AlertListResponse, SafetyAlertResponse
from app.services.admin_alert_service import AdminAlertService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> AdminAlertService:
    return AdminAlertService(session)


@router.get("/alerts/kpis", response_model=StandardResponse[AlertKPIs])
async def get_alert_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminAlertService = Depends(_get_service),
):
    data = await service.get_kpis()
    return StandardResponse(data=AlertKPIs(**data))


@router.get("/alerts/feed", response_model=StandardResponse[AlertListResponse])
async def get_alert_feed(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str | None = Query(None),
    severity: str | None = Query(None),
    status: str | None = Query(None),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminAlertService = Depends(_get_service),
):
    result = await service.get_feed(
        page=page, page_size=page_size,
        category=category, severity=severity, status=status,
    )
    return StandardResponse(data=AlertListResponse(**result))


@router.get("/alerts/{alert_id}", response_model=StandardResponse[SafetyAlertResponse])
async def get_alert_detail(
    alert_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminAlertService = Depends(_get_service),
):
    alert = await service.get_detail(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return StandardResponse(data=SafetyAlertResponse.model_validate(alert))


@router.put("/alerts/{alert_id}/acknowledge", response_model=StandardResponse[SafetyAlertResponse])
async def acknowledge_alert(
    alert_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminAlertService = Depends(_get_service),
):
    alert = await service.acknowledge(alert_id, user.id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return StandardResponse(data=SafetyAlertResponse.model_validate(alert))


@router.put("/alerts/{alert_id}/resolve", response_model=StandardResponse[SafetyAlertResponse])
async def resolve_alert(
    alert_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminAlertService = Depends(_get_service),
):
    alert = await service.resolve(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return StandardResponse(data=SafetyAlertResponse.model_validate(alert))
