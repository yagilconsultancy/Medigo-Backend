from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.incident import (
    CreateIncidentNoteRequest,
    CreateIncidentRequest,
    IncidentKPIs,
    IncidentListResponse,
    IncidentNoteResponse,
    IncidentResponse,
    UpdateIncidentStatusRequest,
)
from app.services.admin_incident_service import AdminIncidentService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> AdminIncidentService:
    return AdminIncidentService(session)


@router.get("/incidents/kpis", response_model=StandardResponse[IncidentKPIs])
async def get_incident_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminIncidentService = Depends(_get_service),
):
    data = await service.get_kpis()
    return StandardResponse(data=IncidentKPIs(**data))


@router.get("/incidents", response_model=StandardResponse[IncidentListResponse])
async def list_incidents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    incident_type: str | None = Query(None),
    status: str | None = Query(None),
    search: str | None = Query(None),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminIncidentService = Depends(_get_service),
):
    result = await service.get_list(
        page=page, page_size=page_size,
        incident_type=incident_type, status=status, search=search,
    )
    return StandardResponse(data=IncidentListResponse(**result))


@router.post("/incidents", response_model=StandardResponse[IncidentResponse])
async def create_incident(
    body: CreateIncidentRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminIncidentService = Depends(_get_service),
):
    incident = await service.create_incident(
        data=body.model_dump(),
        admin_id=user.id,
        admin_name=user.email or "Admin",
    )
    return StandardResponse(data=IncidentResponse.model_validate(incident))


@router.get("/incidents/{incident_id}", response_model=StandardResponse[IncidentResponse])
async def get_incident_detail(
    incident_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminIncidentService = Depends(_get_service),
):
    incident = await service.get_detail(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return StandardResponse(data=IncidentResponse.model_validate(incident))


@router.put("/incidents/{incident_id}/status", response_model=StandardResponse[IncidentResponse])
async def update_incident_status(
    incident_id: UUID,
    body: UpdateIncidentStatusRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminIncidentService = Depends(_get_service),
):
    incident = await service.update_status(incident_id, body.status)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return StandardResponse(data=IncidentResponse.model_validate(incident))


@router.get("/incidents/{incident_id}/notes", response_model=StandardResponse[list[IncidentNoteResponse]])
async def get_incident_notes(
    incident_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminIncidentService = Depends(_get_service),
):
    notes = await service.get_notes(incident_id)
    return StandardResponse(data=[IncidentNoteResponse.model_validate(n) for n in notes])


@router.post("/incidents/{incident_id}/notes", response_model=StandardResponse[IncidentNoteResponse])
async def add_incident_note(
    incident_id: UUID,
    body: CreateIncidentNoteRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminIncidentService = Depends(_get_service),
):
    note = await service.add_note(
        incident_id=incident_id,
        admin_id=user.id,
        admin_name=user.email or "Admin",
        content=body.content,
    )
    return StandardResponse(data=IncidentNoteResponse.model_validate(note))
