from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.pricing_log import PricingLogExportResponse, PricingLogListResponse
from app.services.pricing_log_service import PricingLogService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> PricingLogService:
    return PricingLogService(session)


@router.get("/logs", response_model=StandardResponse[PricingLogListResponse])
async def list_pricing_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: PricingLogService = Depends(_get_service),
):
    data = await service.get_paginated(
        page=page, page_size=page_size, category=category, search=search
    )
    return StandardResponse(data=PricingLogListResponse(**data))


@router.get("/logs/export", response_model=StandardResponse[PricingLogExportResponse])
async def export_pricing_logs(
    category: str | None = Query(default=None),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: PricingLogService = Depends(_get_service),
):
    data = await service.export(category=category)
    return StandardResponse(data=PricingLogExportResponse(**data))
