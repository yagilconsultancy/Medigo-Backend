from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.admin_broadcast import (
    BroadcastKPIs,
    BroadcastListResponse,
    BroadcastResponse,
    SendBroadcastRequest,
)
from app.services.admin_broadcast_service import AdminBroadcastService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> AdminBroadcastService:
    return AdminBroadcastService(session)


# ── System Notifications ──


@router.get("/broadcasts/system/kpis", response_model=StandardResponse[BroadcastKPIs])
async def get_system_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBroadcastService = Depends(_get_service),
):
    data = await service.get_kpis("system")
    return StandardResponse(data=BroadcastKPIs(**data))


@router.get("/broadcasts/system", response_model=StandardResponse[BroadcastListResponse])
async def list_system_broadcasts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBroadcastService = Depends(_get_service),
):
    result = await service.get_history("system", page=page, page_size=page_size)
    return StandardResponse(data=BroadcastListResponse(**result))


@router.post("/broadcasts/system/send", response_model=StandardResponse[BroadcastResponse])
async def send_system_broadcast(
    body: SendBroadcastRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBroadcastService = Depends(_get_service),
):
    broadcast = await service.send_broadcast("system", body.model_dump(), user.id)
    return StandardResponse(data=BroadcastResponse.model_validate(broadcast))


# ── Rider Notifications ──


@router.get("/broadcasts/riders/kpis", response_model=StandardResponse[BroadcastKPIs])
async def get_rider_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBroadcastService = Depends(_get_service),
):
    data = await service.get_kpis("rider")
    return StandardResponse(data=BroadcastKPIs(**data))


@router.get("/broadcasts/riders", response_model=StandardResponse[BroadcastListResponse])
async def list_rider_broadcasts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBroadcastService = Depends(_get_service),
):
    result = await service.get_history("rider", page=page, page_size=page_size)
    return StandardResponse(data=BroadcastListResponse(**result))


@router.post("/broadcasts/riders/send", response_model=StandardResponse[BroadcastResponse])
async def send_rider_broadcast(
    body: SendBroadcastRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBroadcastService = Depends(_get_service),
):
    broadcast = await service.send_broadcast("rider", body.model_dump(), user.id)
    return StandardResponse(data=BroadcastResponse.model_validate(broadcast))


# ── Driver Notifications ──


@router.get("/broadcasts/drivers/kpis", response_model=StandardResponse[BroadcastKPIs])
async def get_driver_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBroadcastService = Depends(_get_service),
):
    data = await service.get_kpis("driver")
    return StandardResponse(data=BroadcastKPIs(**data))


@router.get("/broadcasts/drivers", response_model=StandardResponse[BroadcastListResponse])
async def list_driver_broadcasts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBroadcastService = Depends(_get_service),
):
    result = await service.get_history("driver", page=page, page_size=page_size)
    return StandardResponse(data=BroadcastListResponse(**result))


@router.post("/broadcasts/drivers/send", response_model=StandardResponse[BroadcastResponse])
async def send_driver_broadcast(
    body: SendBroadcastRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBroadcastService = Depends(_get_service),
):
    broadcast = await service.send_broadcast("driver", body.model_dump(), user.id)
    return StandardResponse(data=BroadcastResponse.model_validate(broadcast))


# ── Fleet Notifications ──


@router.get("/broadcasts/fleets/kpis", response_model=StandardResponse[BroadcastKPIs])
async def get_fleet_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBroadcastService = Depends(_get_service),
):
    data = await service.get_kpis("fleet")
    return StandardResponse(data=BroadcastKPIs(**data))


@router.get("/broadcasts/fleets", response_model=StandardResponse[BroadcastListResponse])
async def list_fleet_broadcasts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBroadcastService = Depends(_get_service),
):
    result = await service.get_history("fleet", page=page, page_size=page_size)
    return StandardResponse(data=BroadcastListResponse(**result))


@router.post("/broadcasts/fleets/send", response_model=StandardResponse[BroadcastResponse])
async def send_fleet_broadcast(
    body: SendBroadcastRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminBroadcastService = Depends(_get_service),
):
    broadcast = await service.send_broadcast("fleet", body.model_dump(), user.id)
    return StandardResponse(data=BroadcastResponse.model_validate(broadcast))
