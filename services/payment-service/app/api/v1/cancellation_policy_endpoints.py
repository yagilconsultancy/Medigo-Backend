from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.cancellation_policy import (
    CancellationKPIs,
    CancellationPolicyBulkUpdate,
    CancellationPolicyResponse,
)
from app.services.cancellation_policy_service import CancellationPolicyService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> CancellationPolicyService:
    return CancellationPolicyService(session)


@router.get("/cancellation/kpis", response_model=StandardResponse[CancellationKPIs])
async def get_cancellation_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: CancellationPolicyService = Depends(_get_service),
):
    data = await service.get_kpis()
    return StandardResponse(data=CancellationKPIs(**data))


@router.get("/cancellation", response_model=StandardResponse[CancellationPolicyResponse])
async def get_cancellation_policies(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: CancellationPolicyService = Depends(_get_service),
):
    data = await service.get_all()
    return StandardResponse(data=CancellationPolicyResponse(**data))


@router.put("/cancellation", response_model=StandardResponse[dict])
async def update_cancellation_policies(
    body: CancellationPolicyBulkUpdate,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: CancellationPolicyService = Depends(_get_service),
):
    count = await service.bulk_update(
        [u.model_dump(exclude_unset=True) for u in body.updates],
        admin_id=user.id,
        admin_name=user.email or "Admin",
    )
    return StandardResponse(data={"updated_count": count})
