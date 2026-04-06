from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.stripe_client import StripeClient
from app.clients.ride_service_client import RideServiceClient
from app.config import settings
from app.dependencies import get_db, get_stripe_client, get_publisher
from app.models.fare_breakdown import FareBreakdown
from app.models.payment_method import PaymentMethod
from app.models.transaction import Transaction
from app.repositories.dialysis_rate_plan_repo import DialysisRatePlanRepository
from app.repositories.earnings_period_repo import EarningsPeriodRepository
from app.repositories.earnings_repo import EarningsRepository
from app.repositories.fare_repo import FareBreakdownRepository
from app.repositories.holiday_repo import HolidayRepository
from app.repositories.payment_method_repo import PaymentMethodRepository
from app.repositories.rate_card_repo import RateCardRepository
from app.repositories.service_type_config_repo import ServiceTypeConfigRepository
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
        service_type_repo=ServiceTypeConfigRepository(session),
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
        service_type_repo=ServiceTypeConfigRepository(session),
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
        service_type_repo=ServiceTypeConfigRepository(session),
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


# --- Fleet Revenue Endpoints ---


class FleetEarningsBreakdownRequest(BaseModel):
    business_ids: list[UUID]
    days: int = 30


@router.get(
    "/internal/payments/fleet-revenue-summary",
    dependencies=[Depends(_verify_internal)],
)
async def fleet_revenue_summary(
    business_id: Optional[UUID] = Query(None),
    days: int = Query(default=30, ge=1, le=365),
    session: AsyncSession = Depends(get_db),
):
    """Revenue summary filterable by business_id (fleet)."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)

    conditions = [FareBreakdown.created_at >= since]
    if business_id:
        conditions.append(FareBreakdown.business_id == business_id)

    result = await session.execute(
        select(
            func.coalesce(func.sum(FareBreakdown.total_fare), 0).label("total_revenue"),
            func.coalesce(func.sum(FareBreakdown.driver_earnings), 0).label("total_driver_earnings"),
            func.coalesce(func.sum(FareBreakdown.platform_fee), 0).label("total_platform_fees"),
            func.count().label("fare_count"),
        ).where(*conditions)
    )
    row = result.one()

    return {
        "total_revenue": float(row.total_revenue),
        "total_driver_earnings": float(row.total_driver_earnings),
        "total_platform_fees": float(row.total_platform_fees),
        "fare_count": row.fare_count,
        "period_days": days,
    }


@router.get(
    "/internal/payments/fleet-revenue-trend",
    dependencies=[Depends(_verify_internal)],
)
async def fleet_revenue_trend(
    business_id: Optional[UUID] = Query(None),
    days: int = Query(default=30, ge=1, le=365),
    session: AsyncSession = Depends(get_db),
):
    """Daily revenue trend filterable by business_id."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)

    conditions = [FareBreakdown.created_at >= since]
    if business_id:
        conditions.append(FareBreakdown.business_id == business_id)

    trend_result = await session.execute(
        select(
            cast(FareBreakdown.created_at, Date).label("date"),
            func.sum(FareBreakdown.total_fare).label("revenue"),
            func.count().label("count"),
        )
        .where(*conditions)
        .group_by(cast(FareBreakdown.created_at, Date))
        .order_by(cast(FareBreakdown.created_at, Date))
    )

    trend = [
        {"date": str(r.date), "revenue": float(r.revenue), "count": r.count}
        for r in trend_result.all()
    ]

    return {"trend": trend, "period_days": days}


@router.post(
    "/internal/payments/fleet-earnings-breakdown",
    dependencies=[Depends(_verify_internal)],
)
async def fleet_earnings_breakdown(
    body: FleetEarningsBreakdownRequest,
    session: AsyncSession = Depends(get_db),
):
    """Batch earnings breakdown by business_ids."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=body.days)

    result = await session.execute(
        select(
            FareBreakdown.business_id,
            func.count().label("trips"),
            func.coalesce(func.sum(FareBreakdown.total_fare), 0).label("revenue"),
            func.coalesce(func.sum(FareBreakdown.platform_fee), 0).label("commission"),
            func.coalesce(func.sum(FareBreakdown.driver_earnings), 0).label("net_earnings"),
        )
        .where(
            FareBreakdown.created_at >= since,
            FareBreakdown.business_id.in_(body.business_ids),
        )
        .group_by(FareBreakdown.business_id)
    )

    breakdowns = {}
    for row in result.all():
        bid = str(row.business_id)
        trips = row.trips
        revenue = float(row.revenue)
        breakdowns[bid] = {
            "trips": trips,
            "revenue": revenue,
            "commission": float(row.commission),
            "net_earnings": float(row.net_earnings),
            "avg_per_trip": round(revenue / trips, 2) if trips > 0 else 0.0,
        }

    # Add empty entries for business_ids with no data
    for bid in body.business_ids:
        bid_str = str(bid)
        if bid_str not in breakdowns:
            breakdowns[bid_str] = {
                "trips": 0,
                "revenue": 0.0,
                "commission": 0.0,
                "net_earnings": 0.0,
                "avg_per_trip": 0.0,
            }

    return {"breakdowns": breakdowns}


# --- Rider Endpoints (for admin rider management) ---


@router.get(
    "/internal/riders/{rider_id}/spending",
    dependencies=[Depends(_verify_internal)],
)
async def get_rider_spending(
    rider_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Rider spending summary. Called by user-service for admin rider detail."""
    result = await session.execute(
        select(
            func.count().label("trip_count"),
            func.coalesce(func.sum(Transaction.amount), 0).label("total_spent"),
        ).where(
            Transaction.user_id == rider_id,
            Transaction.transaction_type == "ride_payment",
            Transaction.status == "completed",
        )
    )
    row = result.one()
    trip_count = row.trip_count
    total_spent = float(row.total_spent)
    avg_per_trip = round(total_spent / trip_count, 2) if trip_count > 0 else 0.0

    return {
        "total_spent": total_spent,
        "avg_per_trip": avg_per_trip,
        "trip_count": trip_count,
    }


@router.get(
    "/internal/riders/{rider_id}/payment-methods",
    dependencies=[Depends(_verify_internal)],
)
async def get_rider_payment_methods(
    rider_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Rider payment methods. Called by user-service for admin rider profiles."""
    result = await session.execute(
        select(PaymentMethod).where(
            PaymentMethod.user_id == rider_id,
            PaymentMethod.is_active.is_(True),
            PaymentMethod.deleted_at.is_(None),
        ).order_by(PaymentMethod.is_default.desc())
    )
    methods = list(result.scalars().all())

    return [
        {
            "brand": m.brand,
            "last_four": m.last_four,
            "is_default": m.is_default,
            "method_type": m.method_type,
        }
        for m in methods
    ]
