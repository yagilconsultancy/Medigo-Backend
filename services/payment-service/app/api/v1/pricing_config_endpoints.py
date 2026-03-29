from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.rate_card import RateCard
from app.repositories.rate_card_repo import RateCardRepository
from app.repositories.pricing_change_log_repo import PricingChangeLogRepository
from app.schemas.rate_card import CreateRateCardRequest, RateCardResponse
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


@router.get("/configuration/kpis", response_model=StandardResponse[dict])
async def get_config_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    repo = RateCardRepository(session)
    active = await repo.get_active()
    if not active:
        return StandardResponse(data={
            "avg_trip_fare": 0,
            "base_fare": 0,
            "surge_multiplier": 1.0,
            "cancellation_fee_avg": 0,
        })

    config = active.config or {}
    base_fare = config.get("base_fare", {})
    base = base_fare.get("flat_rate", 0) if isinstance(base_fare, dict) else base_fare

    from sqlalchemy import func, select
    from app.models.fare_breakdown import FareBreakdown
    avg_q = select(func.coalesce(func.avg(FareBreakdown.total_fare), 0))
    avg_result = await session.execute(avg_q)
    avg_fare = float(avg_result.scalar() or 0)

    return StandardResponse(data={
        "avg_trip_fare": round(avg_fare, 2),
        "base_fare": base,
        "surge_multiplier": 1.0,
        "cancellation_fee_avg": 0,
    })


@router.get("/configuration", response_model=StandardResponse[RateCardResponse])
async def get_current_config(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    repo = RateCardRepository(session)
    active = await repo.get_active()
    if not active:
        raise HTTPException(status_code=404, detail="No active rate card found")
    return StandardResponse(data=RateCardResponse.model_validate(active))


@router.put("/configuration", response_model=StandardResponse[RateCardResponse])
async def save_configuration(
    body: CreateRateCardRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    repo = RateCardRepository(session)
    log_repo = PricingChangeLogRepository(session)

    old = await repo.get_active()
    next_version = await repo.get_next_version()
    await repo.deactivate_all()

    new_card = RateCard(
        version=next_version,
        name=body.name,
        config=body.config.model_dump(),
        is_active=True,
        created_by=user.id,
        notes=body.notes,
    )
    new_card = await repo.create(new_card)

    await log_repo.create({
        "admin_id": user.id,
        "admin_name": user.email or "Admin",
        "category": "fare",
        "change_description": f"Updated global fare configuration to v{new_card.version}",
        "before_value": f"v{old.version}" if old else None,
        "after_value": f"v{new_card.version}",
    })

    return StandardResponse(data=RateCardResponse.model_validate(new_card))
