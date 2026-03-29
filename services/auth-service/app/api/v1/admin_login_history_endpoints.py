from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.login_history import (
    LoginHistoryKPIs,
    LoginHistoryListResponse,
)
from app.services.login_history_service import LoginHistoryService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> LoginHistoryService:
    return LoginHistoryService(session)


@router.get("/login-history/kpis", response_model=StandardResponse[LoginHistoryKPIs])
async def get_login_history_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: LoginHistoryService = Depends(_get_service),
):
    data = await service.get_kpis()
    return StandardResponse(data=LoginHistoryKPIs(**data))


@router.get("/login-history", response_model=StandardResponse[LoginHistoryListResponse])
async def list_login_history(
    status: str | None = Query(None, description="all|success|failed"),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: LoginHistoryService = Depends(_get_service),
):
    success_filter = None
    if status == "success":
        success_filter = True
    elif status == "failed":
        success_filter = False

    result = await service.list_records(
        success=success_filter, search=search, page=page, page_size=page_size
    )
    return StandardResponse(data=LoginHistoryListResponse(**result))


@router.get("/login-history/export", response_model=StandardResponse[LoginHistoryListResponse])
async def export_login_history(
    status: str | None = Query(None),
    search: str | None = Query(None),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: LoginHistoryService = Depends(_get_service),
):
    success_filter = None
    if status == "success":
        success_filter = True
    elif status == "failed":
        success_filter = False

    result = await service.list_records(
        success=success_filter, search=search, page=1, page_size=1000
    )
    return StandardResponse(data=LoginHistoryListResponse(**result))
