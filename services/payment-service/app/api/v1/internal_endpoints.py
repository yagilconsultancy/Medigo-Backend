from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.stripe_client import StripeClient
from app.clients.ride_service_client import RideServiceClient
from app.config import settings
from app.dependencies import get_db, get_stripe_client, get_publisher
from app.models.fare_breakdown import FareBreakdown
from app.repositories.dialysis_rate_plan_repo import DialysisRatePlanRepository
from app.repositories.earnings_period_repo import EarningsPeriodRepository
from app.repositories.earnings_repo import EarningsRepository
from app.repositories.fare_repo import FareBreakdownRepository
from app.repositories.holiday_repo import HolidayRepository
from app.repositories.payment_method_repo import PaymentMethodRepository
from app.repositories.rate_card_repo import RateCardRepository
from app.repositories.transaction_repo import TransactionRepository
from app.repositories.weather_condition_repo import WeatherConditionRepository
from app.services.earnings_service import EarningsService
from app.services.fare_service import FareService
from app.services.payment_processing_service import PaymentProcessingService
from mediride_common.events.publisher import EventPublisher

router = APIRouter()


def _verify_internal(x_internal_service: str = Header(None)):
    if not x_internal_service:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Internal access only")


class ChargeRideRequest(BaseModel):
    ride_id: UUID
    rider_id: UUID
    driver_id: UUID


class RefundRideRequest(BaseModel):
    ride_id: UUID
    rider_id: UUID


@router.post(
    "/internal/payments/calculate-fare",
    dependencies=[Depends(_verify_internal)],
)
async def calculate_fare(
    ride_data: dict,
    session: AsyncSession = Depends(get_db),
):
    service = FareService(
        fare_repo=FareBreakdownRepository(session),
        rate_card_repo=RateCardRepository(session),
        holiday_repo=HolidayRepository(session),
        weather_repo=WeatherConditionRepository(session),
        dialysis_repo=DialysisRatePlanRepository(session),
    )
    breakdown = await service.calculate_fare(ride_data)
    return {
        "ride_id": str(breakdown.ride_id),
        "total_fare": float(breakdown.total_fare),
        "driver_earnings": float(breakdown.driver_earnings),
        "base_fare": float(breakdown.base_fare),
        "distance_charge": float(breakdown.distance_charge),
        "platform_fee": float(breakdown.platform_fee),
        "rate_card_version": breakdown.rate_card_version,
    }


@router.post(
    "/internal/payments/record-earnings",
    dependencies=[Depends(_verify_internal)],
)
async def record_earnings(
    data: dict,
    session: AsyncSession = Depends(get_db),
):
    service = EarningsService(
        earnings_repo=EarningsRepository(session),
        period_repo=EarningsPeriodRepository(session),
        tx_repo=TransactionRepository(session),
        fare_repo=FareBreakdownRepository(session),
    )
    await service.record_ride_earnings(
        ride_id=data["ride_id"],
        driver_id=data["driver_id"],
        fare_amount=data["fare_amount"],
    )
    return {"status": "ok"}


@router.post(
    "/internal/payments/charge-ride",
    dependencies=[Depends(_verify_internal)],
)
async def charge_ride(
    body: ChargeRideRequest,
    session: AsyncSession = Depends(get_db),
    stripe: StripeClient = Depends(get_stripe_client),
    publisher: EventPublisher = Depends(get_publisher),
):
    """Charge a rider for a completed ride via Stripe."""
    service = PaymentProcessingService(
        tx_repo=TransactionRepository(session),
        fare_repo=FareBreakdownRepository(session),
        pm_repo=PaymentMethodRepository(session),
        earnings_repo=EarningsRepository(session),
        rate_card_repo=RateCardRepository(session),
        holiday_repo=HolidayRepository(session),
        weather_repo=WeatherConditionRepository(session),
        dialysis_repo=DialysisRatePlanRepository(session),
        stripe_client=stripe,
        ride_client=RideServiceClient(settings.RIDE_SERVICE_URL),
        publisher=publisher,
    )
    tx = await service.process_ride_payment(
        ride_id=body.ride_id,
        rider_id=body.rider_id,
        driver_id=body.driver_id,
    )
    return {
        "transaction_id": str(tx.id),
        "status": tx.status,
        "amount": float(tx.amount),
    }


@router.post(
    "/internal/payments/refund-ride",
    dependencies=[Depends(_verify_internal)],
)
async def refund_ride(
    body: RefundRideRequest,
    session: AsyncSession = Depends(get_db),
    stripe: StripeClient = Depends(get_stripe_client),
    publisher: EventPublisher = Depends(get_publisher),
):
    """Refund a ride payment via Stripe."""
    service = PaymentProcessingService(
        tx_repo=TransactionRepository(session),
        fare_repo=FareBreakdownRepository(session),
        pm_repo=PaymentMethodRepository(session),
        earnings_repo=EarningsRepository(session),
        rate_card_repo=RateCardRepository(session),
        holiday_repo=HolidayRepository(session),
        weather_repo=WeatherConditionRepository(session),
        dialysis_repo=DialysisRatePlanRepository(session),
        stripe_client=stripe,
        ride_client=RideServiceClient(settings.RIDE_SERVICE_URL),
        publisher=publisher,
    )
    refund_tx = await service.refund_ride_payment(
        ride_id=body.ride_id,
        rider_id=body.rider_id,
    )
    if refund_tx:
        return {
            "transaction_id": str(refund_tx.id),
            "status": refund_tx.status,
            "amount": float(refund_tx.amount),
        }
    return {"status": "no_payment_to_refund"}


@router.get(
    "/internal/payments/revenue-summary",
    dependencies=[Depends(_verify_internal)],
)
async def revenue_summary(
    days: int = Query(default=30, ge=1, le=365),
    session: AsyncSession = Depends(get_db),
):
    """Return total revenue, driver earnings, and platform fees for a period."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)

    result = await session.execute(
        select(
            func.coalesce(func.sum(FareBreakdown.total_fare), 0).label("total_revenue"),
            func.coalesce(func.sum(FareBreakdown.driver_earnings), 0).label("total_driver_earnings"),
            func.coalesce(func.sum(FareBreakdown.platform_fee), 0).label("total_platform_fees"),
            func.count().label("fare_count"),
        ).where(FareBreakdown.created_at >= since)
    )
    row = result.one()

    # Daily revenue trend
    trend_result = await session.execute(
        select(
            cast(FareBreakdown.created_at, Date).label("date"),
            func.sum(FareBreakdown.total_fare).label("revenue"),
            func.count().label("count"),
        )
        .where(FareBreakdown.created_at >= since)
        .group_by(cast(FareBreakdown.created_at, Date))
        .order_by(cast(FareBreakdown.created_at, Date))
    )
    trend = [
        {"date": str(r.date), "revenue": float(r.revenue), "count": r.count}
        for r in trend_result.all()
    ]

    return {
        "total_revenue": float(row.total_revenue),
        "total_driver_earnings": float(row.total_driver_earnings),
        "total_platform_fees": float(row.total_platform_fees),
        "fare_count": row.fare_count,
        "period_days": days,
        "trend": trend,
    }
