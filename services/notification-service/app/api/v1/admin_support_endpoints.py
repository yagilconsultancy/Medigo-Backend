from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.admin_support import (
    ResolveTicketRequest,
    SupportKPIs,
    SupportTicketListResponse,
)
from app.services.admin_support_service import AdminSupportService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> AdminSupportService:
    return AdminSupportService(session)


@router.get("/support/kpis", response_model=StandardResponse[SupportKPIs])
async def get_support_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminSupportService = Depends(_get_service),
):
    data = await service.get_kpis()
    return StandardResponse(data=SupportKPIs(**data))


@router.get("/support/tickets", response_model=StandardResponse[SupportTicketListResponse])
async def list_support_tickets(
    status: str | None = Query(None, description="all|open|under_review|resolved"),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminSupportService = Depends(_get_service),
):
    status_filter = status if status and status != "all" else None
    result = await service.list_tickets(status=status_filter, search=search, page=page, page_size=page_size)
    return StandardResponse(data=SupportTicketListResponse(**result))


@router.put("/support/tickets/{ticket_id}/open", response_model=StandardResponse[dict])
async def reopen_ticket(
    ticket_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminSupportService = Depends(_get_service),
):
    result = await service.reopen_ticket(ticket_id)
    return StandardResponse(data=result, message="Ticket reopened")


@router.put("/support/tickets/{ticket_id}/resolve", response_model=StandardResponse[dict])
async def resolve_ticket(
    ticket_id: UUID,
    body: ResolveTicketRequest | None = None,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminSupportService = Depends(_get_service),
):
    response_text = body.response if body else None
    result = await service.resolve_ticket(ticket_id, user.id, response_text)
    return StandardResponse(data=result, message="Ticket resolved")
