from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.disciplinary_action import (
    CreateDisciplinaryActionRequest,
    DisciplinaryActionResponse,
    DisciplinaryKPIs,
    DisciplinaryListResponse,
    DisciplinaryReasonResponse,
)
from app.services.admin_discipline_service import AdminDisciplineService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> AdminDisciplineService:
    return AdminDisciplineService(session)


@router.get("/disciplinary/kpis", response_model=StandardResponse[DisciplinaryKPIs])
async def get_disciplinary_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDisciplineService = Depends(_get_service),
):
    data = await service.get_kpis()
    return StandardResponse(data=DisciplinaryKPIs(**data))


@router.get("/disciplinary", response_model=StandardResponse[DisciplinaryListResponse])
async def list_disciplinary_actions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    search: str | None = Query(None),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDisciplineService = Depends(_get_service),
):
    result = await service.get_list(
        page=page, page_size=page_size, status=status, search=search,
    )
    return StandardResponse(data=DisciplinaryListResponse(**result))


@router.post("/disciplinary", response_model=StandardResponse[DisciplinaryActionResponse])
async def create_disciplinary_action(
    body: CreateDisciplinaryActionRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDisciplineService = Depends(_get_service),
):
    action = await service.create_action(
        data=body.model_dump(),
        admin_id=user.id,
        admin_name=user.email or "Admin",
    )
    return StandardResponse(data=DisciplinaryActionResponse.model_validate(action))


@router.get("/disciplinary/{action_id}", response_model=StandardResponse[DisciplinaryActionResponse])
async def get_disciplinary_detail(
    action_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDisciplineService = Depends(_get_service),
):
    action = await service.get_detail(action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Disciplinary action not found")
    return StandardResponse(data=DisciplinaryActionResponse.model_validate(action))


@router.get("/disciplinary/{action_id}/reason", response_model=StandardResponse[DisciplinaryReasonResponse])
async def get_disciplinary_reason(
    action_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDisciplineService = Depends(_get_service),
):
    reason = await service.get_reason(action_id)
    if reason is None:
        raise HTTPException(status_code=404, detail="Disciplinary action not found")
    return StandardResponse(data=DisciplinaryReasonResponse(reason=reason))


@router.put("/disciplinary/{action_id}/reinstate", response_model=StandardResponse[DisciplinaryActionResponse])
async def reinstate_disciplinary_action(
    action_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDisciplineService = Depends(_get_service),
):
    action = await service.reinstate(action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Disciplinary action not found")
    return StandardResponse(data=DisciplinaryActionResponse.model_validate(action))


@router.put("/disciplinary/{action_id}/collapse", response_model=StandardResponse[DisciplinaryActionResponse])
async def toggle_collapse_disciplinary(
    action_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDisciplineService = Depends(_get_service),
):
    action = await service.get_detail_toggle(action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Disciplinary action not found")
    return StandardResponse(data=DisciplinaryActionResponse.model_validate(action))
