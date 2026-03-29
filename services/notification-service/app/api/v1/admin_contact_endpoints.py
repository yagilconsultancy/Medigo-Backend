from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.admin_support import (
    ContactLogItem,
    ContactLogKPIs,
    ContactLogListResponse,
    CreateContactLogRequest,
)
from app.services.contact_log_service import ContactLogService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> ContactLogService:
    return ContactLogService(session)


@router.get("/contact-logs/kpis", response_model=StandardResponse[ContactLogKPIs])
async def get_contact_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: ContactLogService = Depends(_get_service),
):
    data = await service.get_kpis()
    return StandardResponse(data=ContactLogKPIs(**data))


@router.get("/contact-logs", response_model=StandardResponse[ContactLogListResponse])
async def list_contact_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: ContactLogService = Depends(_get_service),
):
    result = await service.list_recent(page=page, page_size=page_size)
    return StandardResponse(data=ContactLogListResponse(**result))


@router.post("/contact-logs", response_model=StandardResponse[ContactLogItem])
async def create_contact_log(
    body: CreateContactLogRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: ContactLogService = Depends(_get_service),
):
    log = await service.create_log(
        user_id=body.user_id,
        user_name=body.user_name,
        user_role=body.user_role,
        channel=body.channel,
        description=body.description,
        agent_id=user.id,
        agent_name=body.agent_name,
        duration_seconds=body.duration_seconds,
        outcome=body.outcome,
    )
    return StandardResponse(
        data=ContactLogItem.model_validate(log),
        message="Contact log created",
    )
