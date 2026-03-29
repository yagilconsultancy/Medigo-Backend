from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.investigation import (
    AssignInvestigatorRequest,
    CreateInvestigationNoteRequest,
    InvestigationKPIs,
    InvestigationListResponse,
    InvestigationNoteResponse,
    InvestigationResponse,
    UpdateInvestigationStatusRequest,
    UpdateProgressRequest,
)
from app.services.admin_investigation_service import AdminInvestigationService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> AdminInvestigationService:
    return AdminInvestigationService(session)


@router.get("/investigations/kpis", response_model=StandardResponse[InvestigationKPIs])
async def get_investigation_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminInvestigationService = Depends(_get_service),
):
    data = await service.get_kpis()
    return StandardResponse(data=InvestigationKPIs(**data))


@router.get("/investigations", response_model=StandardResponse[InvestigationListResponse])
async def list_investigations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    priority: str | None = Query(None),
    status: str | None = Query(None),
    search: str | None = Query(None),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminInvestigationService = Depends(_get_service),
):
    result = await service.get_list(
        page=page, page_size=page_size,
        priority=priority, status=status, search=search,
    )
    return StandardResponse(data=InvestigationListResponse(**result))


@router.get("/investigations/{inv_id}", response_model=StandardResponse[InvestigationResponse])
async def get_investigation_detail(
    inv_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminInvestigationService = Depends(_get_service),
):
    inv = await service.get_detail(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return StandardResponse(data=InvestigationResponse.model_validate(inv))


@router.put("/investigations/{inv_id}/assign", response_model=StandardResponse[InvestigationResponse])
async def assign_investigator(
    inv_id: UUID,
    body: AssignInvestigatorRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminInvestigationService = Depends(_get_service),
):
    inv = await service.assign(inv_id, body.assigned_to_id, body.assigned_to_name)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return StandardResponse(data=InvestigationResponse.model_validate(inv))


@router.put("/investigations/{inv_id}/status", response_model=StandardResponse[InvestigationResponse])
async def update_investigation_status(
    inv_id: UUID,
    body: UpdateInvestigationStatusRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminInvestigationService = Depends(_get_service),
):
    inv = await service.update_status(inv_id, body.status)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return StandardResponse(data=InvestigationResponse.model_validate(inv))


@router.put("/investigations/{inv_id}/progress", response_model=StandardResponse[InvestigationResponse])
async def update_investigation_progress(
    inv_id: UUID,
    body: UpdateProgressRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminInvestigationService = Depends(_get_service),
):
    inv = await service.update_progress(inv_id, body.progress_percent)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return StandardResponse(data=InvestigationResponse.model_validate(inv))


@router.put("/investigations/{inv_id}/close", response_model=StandardResponse[InvestigationResponse])
async def close_investigation(
    inv_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminInvestigationService = Depends(_get_service),
):
    inv = await service.close(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return StandardResponse(data=InvestigationResponse.model_validate(inv))


@router.get("/investigations/{inv_id}/notes", response_model=StandardResponse[list[InvestigationNoteResponse]])
async def get_investigation_notes(
    inv_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminInvestigationService = Depends(_get_service),
):
    notes = await service.get_notes(inv_id)
    return StandardResponse(data=[InvestigationNoteResponse.model_validate(n) for n in notes])


@router.post("/investigations/{inv_id}/notes", response_model=StandardResponse[InvestigationNoteResponse])
async def add_investigation_note(
    inv_id: UUID,
    body: CreateInvestigationNoteRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminInvestigationService = Depends(_get_service),
):
    note = await service.add_note(
        inv_id=inv_id,
        admin_id=user.id,
        admin_name=user.email or "Admin",
        content=body.content,
    )
    return StandardResponse(data=InvestigationNoteResponse.model_validate(note))
