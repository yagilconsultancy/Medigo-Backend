from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.moneris_client import MonerisClient
from app.clients.ride_service_client import RideServiceClient
from app.config import settings
from app.dependencies import get_db, get_moneris_client, get_publisher
from app.repositories.earnings_period_repo import EarningsPeriodRepository
from app.repositories.earnings_repo import EarningsRepository
from app.repositories.fare_repo import FareBreakdownRepository
from app.repositories.payment_method_repo import PaymentMethodRepository
from app.repositories.transaction_repo import TransactionRepository
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
    service = FareService(fare_repo=FareBreakdownRepository(session))
    breakdown = await service.calculate_fare(ride_data)
    return {
        "ride_id": str(breakdown.ride_id),
        "total_fare": float(breakdown.total_fare),
        "driver_earnings": float(breakdown.driver_earnings),
        "base_fare": float(breakdown.base_fare),
        "distance_charge": float(breakdown.distance_charge),
        "medical_assist_premium": float(breakdown.medical_assist_premium),
        "service_fee": float(breakdown.service_fee),
        "platform_fee": float(breakdown.platform_fee),
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
    moneris: MonerisClient = Depends(get_moneris_client),
    publisher: EventPublisher = Depends(get_publisher),
):
    """Charge a rider for a completed ride via Moneris."""
    service = PaymentProcessingService(
        tx_repo=TransactionRepository(session),
        fare_repo=FareBreakdownRepository(session),
        pm_repo=PaymentMethodRepository(session),
        earnings_repo=EarningsRepository(session),
        moneris_client=moneris,
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
    moneris: MonerisClient = Depends(get_moneris_client),
    publisher: EventPublisher = Depends(get_publisher),
):
    """Refund a ride payment via Moneris."""
    service = PaymentProcessingService(
        tx_repo=TransactionRepository(session),
        fare_repo=FareBreakdownRepository(session),
        pm_repo=PaymentMethodRepository(session),
        earnings_repo=EarningsRepository(session),
        moneris_client=moneris,
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
