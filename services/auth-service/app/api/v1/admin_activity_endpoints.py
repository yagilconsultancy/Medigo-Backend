from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.activity_log import (
    ActivityLogItem,
    ActivityLogKPIs,
    ActivityLogListResponse,
    CreateActivityLogRequest,
)
from app.services.activity_log_service import ActivityLogService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> ActivityLogService:
    return ActivityLogService(session)


@router.get("/activity-logs/kpis", response_model=StandardResponse[ActivityLogKPIs])
async def get_activity_log_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: ActivityLogService = Depends(_get_service),
):
    data = await service.get_kpis()
    return StandardResponse(data=ActivityLogKPIs(**data))


@router.get("/activity-logs", response_model=StandardResponse[ActivityLogListResponse])
async def list_activity_logs(
    severity: str | None = Query(None, description="all|info|warning|critical"),
    category: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: ActivityLogService = Depends(_get_service),
):
    severity_filter = severity if severity and severity != "all" else None
    result = await service.list_logs(
        severity=severity_filter, category=category, search=search, page=page, page_size=page_size
    )
    return StandardResponse(data=ActivityLogListResponse(**result))


@router.get("/activity-logs/export", response_model=StandardResponse[ActivityLogListResponse])
async def export_activity_logs(
    severity: str | None = Query(None),
    category: str | None = Query(None),
    search: str | None = Query(None),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: ActivityLogService = Depends(_get_service),
):
    severity_filter = severity if severity and severity != "all" else None
    result = await service.list_logs(
        severity=severity_filter, category=category, search=search, page=1, page_size=1000
    )
    return StandardResponse(data=ActivityLogListResponse(**result))
