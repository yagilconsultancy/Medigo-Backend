from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories.earnings_period_repo import EarningsPeriodRepository
from app.repositories.earnings_repo import EarningsRepository
from app.repositories.fare_repo import FareBreakdownRepository
from app.repositories.transaction_repo import TransactionRepository
from app.schemas.earnings import (
    EarningsBalanceResponse,
    EarningsBreakdownRequest,
    EarningsBreakdownResponse,
    EarningsHistoryItem,
    EarningsSummaryResponse,
    PerformanceDataPoint,
)
from app.services.earnings_service import EarningsService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_earnings_service(session: AsyncSession = Depends(get_db)) -> EarningsService:
    return EarningsService(
        earnings_repo=EarningsRepository(session),
        period_repo=EarningsPeriodRepository(session),
        tx_repo=TransactionRepository(session),
        fare_repo=FareBreakdownRepository(session),
    )


@router.get("/balance", response_model=StandardResponse[EarningsBalanceResponse])
async def get_balance(
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: EarningsService = Depends(_get_earnings_service),
):
    data = await service.get_driver_balance(user.id)
    return StandardResponse(data=EarningsBalanceResponse(**data))


@router.get("/summary", response_model=StandardResponse[EarningsSummaryResponse])
async def get_earnings_summary(
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: EarningsService = Depends(_get_earnings_service),
):
    data = await service.get_earnings_summary(user.id)
    return StandardResponse(data=EarningsSummaryResponse(**data))


@router.get("/breakdown", response_model=StandardResponse[EarningsBreakdownResponse])
async def get_earnings_breakdown(
    period_type: str = Query("weekly"),
    start_date: date = Query(...),
    end_date: date = Query(...),
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: EarningsService = Depends(_get_earnings_service),
):
    data = await service.get_earnings_breakdown(user.id, period_type, start_date, end_date)
    return StandardResponse(data=EarningsBreakdownResponse(**data))


@router.get("/performance", response_model=StandardResponse[list[PerformanceDataPoint]])
async def get_performance(
    period_type: str = Query("weekly"),
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: EarningsService = Depends(_get_earnings_service),
):
    data = await service.get_performance_data(user.id, period_type)
    return StandardResponse(data=[PerformanceDataPoint(**d) for d in data])


@router.get("/history", response_model=StandardResponse[list[EarningsHistoryItem]])
async def get_earnings_history(
    days: int = Query(7, ge=1, le=90),
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: EarningsService = Depends(_get_earnings_service),
):
    data = await service.get_recent_history(user.id, days)
    return StandardResponse(data=[EarningsHistoryItem(**d) for d in data])
