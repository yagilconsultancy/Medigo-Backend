from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.dialysis_rate_plan import DialysisRatePlan
from app.models.holiday import Holiday
from app.models.rate_card import RateCard
from app.repositories.dialysis_rate_plan_repo import DialysisRatePlanRepository
from app.repositories.fare_repo import FareBreakdownRepository
from app.repositories.holiday_repo import HolidayRepository
from app.repositories.rate_card_repo import RateCardRepository
from app.repositories.weather_condition_repo import WeatherConditionRepository
from app.schemas.rate_card import (
    CreateRateCardRequest,
    DialysisRatePlanCreateRequest,
    DialysisRatePlanResponse,
    DialysisRatePlanUpdateRequest,
    FareEstimateRequest,
    FareEstimateResponse,
    HolidayCreateRequest,
    HolidayResponse,
    RateCardResponse,
    RateCardSummaryResponse,
    WeatherConditionResponse,
    WeatherToggleRequest,
)
from app.services.fare_service import FareService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.exceptions import NotFoundError
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


# ---- Helper to build repos ----

def _repos(session: AsyncSession):
    return {
        "rate_card_repo": RateCardRepository(session),
        "holiday_repo": HolidayRepository(session),
        "weather_repo": WeatherConditionRepository(session),
        "dialysis_repo": DialysisRatePlanRepository(session),
        "fare_repo": FareBreakdownRepository(session),
    }


# ===================== Rate Cards =====================

@router.post("", response_model=StandardResponse[RateCardResponse])
async def create_rate_card(
    body: CreateRateCardRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    """Create and activate a new rate card version."""
    repos = _repos(session)
    repo = repos["rate_card_repo"]

    next_version = await repo.get_next_version()
    await repo.deactivate_all()

    card = RateCard(
        version=next_version,
        name=body.name,
        config=body.config.model_dump(),
        is_active=True,
        created_by=user.id,
        notes=body.notes,
    )
    card = await repo.create(card)
    await session.commit()

    return StandardResponse(data=RateCardResponse.model_validate(card))


@router.get("", response_model=StandardResponse[list[RateCardSummaryResponse]])
async def list_rate_cards(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    """List all rate card versions (paginated)."""
    repo = RateCardRepository(session)
    cards = await repo.get_all(limit=limit, offset=offset)
    return StandardResponse(
        data=[RateCardSummaryResponse.model_validate(c) for c in cards]
    )


@router.get("/active", response_model=StandardResponse[RateCardResponse])
async def get_active_rate_card(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    """Get the currently active rate card."""
    repo = RateCardRepository(session)
    card = await repo.get_active()
    if not card:
        raise NotFoundError("No active rate card found")
    return StandardResponse(data=RateCardResponse.model_validate(card))


# ===================== Holidays =====================

@router.post("/holidays", response_model=StandardResponse[HolidayResponse])
async def create_holiday(
    body: HolidayCreateRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    """Add a new holiday."""
    repo = HolidayRepository(session)
    holiday = Holiday(
        date=body.date,
        name=body.name,
        created_by=user.id,
    )
    holiday = await repo.create(holiday)
    await session.commit()
    return StandardResponse(data=HolidayResponse.model_validate(holiday))


@router.get("/holidays", response_model=StandardResponse[list[HolidayResponse]])
async def list_holidays(
    year: int | None = Query(default=None),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    """List holidays, optionally filtered by year."""
    repo = HolidayRepository(session)
    holidays = await repo.get_all(year=year)
    return StandardResponse(
        data=[HolidayResponse.model_validate(h) for h in holidays]
    )


@router.delete("/holidays/{holiday_id}", response_model=StandardResponse[dict])
async def delete_holiday(
    holiday_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    """Remove a holiday."""
    repo = HolidayRepository(session)
    deleted = await repo.delete_by_id(holiday_id)
    if not deleted:
        raise NotFoundError("Holiday not found")
    await session.commit()
    return StandardResponse(data={"deleted": True})


# ===================== Weather =====================

@router.get("/weather", response_model=StandardResponse[list[WeatherConditionResponse]])
async def list_weather_conditions(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    """Get all weather conditions and their toggle state."""
    repo = WeatherConditionRepository(session)
    conditions = await repo.get_all()
    return StandardResponse(
        data=[WeatherConditionResponse.model_validate(c) for c in conditions]
    )


@router.put("/weather", response_model=StandardResponse[WeatherConditionResponse])
async def toggle_weather_condition(
    body: WeatherToggleRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    """Toggle a weather surcharge condition on/off."""
    repo = WeatherConditionRepository(session)
    condition = await repo.toggle(
        condition_type=body.condition_type,
        is_active=body.is_active,
        activated_by=user.id,
        notes=body.notes,
    )
    if not condition:
        raise NotFoundError(f"Weather condition '{body.condition_type}' not found")
    await session.commit()
    return StandardResponse(data=WeatherConditionResponse.model_validate(condition))


# ===================== Dialysis Plans =====================

@router.post("/dialysis-plans", response_model=StandardResponse[DialysisRatePlanResponse])
async def create_dialysis_plan(
    body: DialysisRatePlanCreateRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    """Create a new dialysis rate plan."""
    repo = DialysisRatePlanRepository(session)
    plan = DialysisRatePlan(
        plan_name=body.plan_name,
        origin_area=body.origin_area,
        destination_area=body.destination_area,
        per_trip_rate=body.per_trip_rate,
        monthly_package_rate=body.monthly_package_rate,
        monthly_package_trips=body.monthly_package_trips,
        min_trips_per_week=body.min_trips_per_week,
        is_active=True,
        created_by=user.id,
    )
    plan = await repo.create(plan)
    await session.commit()
    return StandardResponse(data=DialysisRatePlanResponse.model_validate(plan))


@router.get("/dialysis-plans", response_model=StandardResponse[list[DialysisRatePlanResponse]])
async def list_dialysis_plans(
    active_only: bool = Query(default=False),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    """List all dialysis rate plans."""
    repo = DialysisRatePlanRepository(session)
    plans = await repo.get_all(active_only=active_only)
    return StandardResponse(
        data=[DialysisRatePlanResponse.model_validate(p) for p in plans]
    )


@router.put("/dialysis-plans/{plan_id}", response_model=StandardResponse[DialysisRatePlanResponse])
async def update_dialysis_plan(
    plan_id: UUID,
    body: DialysisRatePlanUpdateRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    """Update a dialysis rate plan."""
    repo = DialysisRatePlanRepository(session)
    update_data = body.model_dump(exclude_unset=True)
    plan = await repo.update(plan_id, **update_data)
    if not plan:
        raise NotFoundError("Dialysis rate plan not found")
    await session.commit()
    return StandardResponse(data=DialysisRatePlanResponse.model_validate(plan))


@router.delete("/dialysis-plans/{plan_id}", response_model=StandardResponse[DialysisRatePlanResponse])
async def deactivate_dialysis_plan(
    plan_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    """Deactivate (soft-delete) a dialysis rate plan."""
    repo = DialysisRatePlanRepository(session)
    plan = await repo.deactivate(plan_id)
    if not plan:
        raise NotFoundError("Dialysis rate plan not found")
    await session.commit()
    return StandardResponse(data=DialysisRatePlanResponse.model_validate(plan))


# ===================== Fare Estimate =====================

@router.post("/estimate-fare", response_model=StandardResponse[FareEstimateResponse])
async def estimate_fare(
    body: FareEstimateRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    """Calculate a fare estimate without persisting."""
    repos = _repos(session)
    fare_service = FareService(
        fare_repo=repos["fare_repo"],
        rate_card_repo=repos["rate_card_repo"],
        holiday_repo=repos["holiday_repo"],
        weather_repo=repos["weather_repo"],
        dialysis_repo=repos["dialysis_repo"],
    )
    estimate = await fare_service.estimate_fare({
        "distance_miles": body.distance_miles,
        "scheduled_at": body.scheduled_at.isoformat(),
        "pickup_address": body.pickup_address,
        "destination_address": body.destination_address,
        "use_highway_407": body.use_highway_407,
        "highway_407_route": body.highway_407_route,
        "is_dialysis_trip": body.is_dialysis_trip,
        "timeline": [],
    })
    return StandardResponse(data=FareEstimateResponse(**estimate))


# ===================== Rate Card by ID (must be last - dynamic path) =====================

@router.get("/{card_id}", response_model=StandardResponse[RateCardResponse])
async def get_rate_card(
    card_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    """Get a specific rate card by ID."""
    repo = RateCardRepository(session)
    card = await repo.get_by_id(card_id)
    if not card:
        raise NotFoundError("Rate card not found")
    return StandardResponse(data=RateCardResponse.model_validate(card))


@router.post("/{card_id}/activate", response_model=StandardResponse[RateCardResponse])
async def activate_rate_card(
    card_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    """Activate a specific rate card version (deactivates all others)."""
    repo = RateCardRepository(session)
    card = await repo.activate(card_id)
    if not card:
        raise NotFoundError("Rate card not found")
    await session.commit()
    return StandardResponse(data=RateCardResponse.model_validate(card))
