from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.surcharge_rule import (
    SurchargeKPIs,
    SurchargeRuleCreate,
    SurchargeRuleListResponse,
    SurchargeRuleResponse,
    SurchargeRuleUpdate,
)
from app.services.surcharge_rule_service import SurchargeRuleService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> SurchargeRuleService:
    return SurchargeRuleService(session)


@router.get("/surcharges/kpis", response_model=StandardResponse[SurchargeKPIs])
async def get_surcharge_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: SurchargeRuleService = Depends(_get_service),
):
    data = await service.get_kpis()
    return StandardResponse(data=SurchargeKPIs(**data))


@router.get("/surcharges", response_model=StandardResponse[SurchargeRuleListResponse])
async def list_surcharge_rules(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: SurchargeRuleService = Depends(_get_service),
):
    rules = await service.get_all()
    return StandardResponse(data=SurchargeRuleListResponse(rules=rules))


@router.post("/surcharges", response_model=StandardResponse[SurchargeRuleResponse])
async def create_surcharge_rule(
    body: SurchargeRuleCreate,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: SurchargeRuleService = Depends(_get_service),
):
    data = await service.create(
        body.model_dump(exclude_unset=True),
        admin_id=user.id,
        admin_name=user.email or "Admin",
    )
    return StandardResponse(data=SurchargeRuleResponse(**data))


@router.put("/surcharges/{rule_id}", response_model=StandardResponse[SurchargeRuleResponse])
async def update_surcharge_rule(
    rule_id: UUID,
    body: SurchargeRuleUpdate,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: SurchargeRuleService = Depends(_get_service),
):
    data = await service.update(
        rule_id,
        body.model_dump(exclude_unset=True),
        admin_id=user.id,
        admin_name=user.email or "Admin",
    )
    if not data:
        raise HTTPException(status_code=404, detail="Surcharge rule not found")
    return StandardResponse(data=SurchargeRuleResponse(**data))


@router.delete("/surcharges/{rule_id}", response_model=StandardResponse[dict])
async def delete_surcharge_rule(
    rule_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: SurchargeRuleService = Depends(_get_service),
):
    deleted = await service.delete(
        rule_id, admin_id=user.id, admin_name=user.email or "Admin"
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Surcharge rule not found")
    return StandardResponse(data={"deleted": True})
