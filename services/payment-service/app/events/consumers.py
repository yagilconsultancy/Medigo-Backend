import logging
from uuid import UUID

from app.config import settings
from app.clients.stripe_client import StripeClient
from app.clients.ride_service_client import RideServiceClient
from app.dependencies import get_broker, get_db, get_stripe_client, get_publisher
from app.repositories.dialysis_rate_plan_repo import DialysisRatePlanRepository
from app.repositories.earnings_repo import EarningsRepository
from app.repositories.fare_repo import FareBreakdownRepository
from app.repositories.holiday_repo import HolidayRepository
from app.repositories.payment_method_repo import PaymentMethodRepository
from app.repositories.rate_card_repo import RateCardRepository
from app.repositories.service_type_config_repo import ServiceTypeConfigRepository
from app.repositories.transaction_repo import TransactionRepository
from app.repositories.weather_condition_repo import WeatherConditionRepository
from app.services.payment_processing_service import PaymentProcessingService
from mediride_common.events.constants import Exchanges, Queues, RoutingKeys
from mediride_common.events.consumer import BaseEventConsumer
from mediride_common.events.schemas import EventEnvelope, RideStatusChangedPayload

logger = logging.getLogger(__name__)


class RideCompletedConsumer(BaseEventConsumer):
    """When a ride is completed, charge the rider and record driver earnings."""

    async def handle(self, envelope: EventEnvelope) -> None:
        if envelope.event_type != RoutingKeys.RIDE_COMPLETED:
            return

        payload = RideStatusChangedPayload(**envelope.payload)
        logger.info(f"Ride completed: {payload.ride_id}, processing payment")

        if not payload.driver_id:
            logger.warning(f"Ride {payload.ride_id} completed without driver_id, skipping payment")
            return

        async for session in get_db():
            try:
                service = PaymentProcessingService(
                    tx_repo=TransactionRepository(session),
                    fare_repo=FareBreakdownRepository(session),
                    pm_repo=PaymentMethodRepository(session),
                    earnings_repo=EarningsRepository(session),
                    rate_card_repo=RateCardRepository(session),
                    holiday_repo=HolidayRepository(session),
                    weather_repo=WeatherConditionRepository(session),
                    dialysis_repo=DialysisRatePlanRepository(session),
                    stripe_client=get_stripe_client(),
                    ride_client=RideServiceClient(settings.RIDE_SERVICE_URL),
                    publisher=get_publisher(),
                    service_type_repo=ServiceTypeConfigRepository(session),
                )

                tx = await service.process_ride_payment(
                    ride_id=payload.ride_id,
                    rider_id=payload.rider_id,
                    driver_id=payload.driver_id,
                )

                logger.info(
                    f"Ride {payload.ride_id} payment processed: "
                    f"status={tx.status}, amount=${float(tx.amount)}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to process payment for ride {payload.ride_id}: {e}",
                    exc_info=True,
                )


class RideCancelledConsumer(BaseEventConsumer):
    """Handle ride cancellation - refund if payment was already processed."""

    async def handle(self, envelope: EventEnvelope) -> None:
        if envelope.event_type != RoutingKeys.RIDE_CANCELLED:
            return

        payload = RideStatusChangedPayload(**envelope.payload)
        logger.info(f"Ride cancelled: {payload.ride_id}, checking for refund")

        async for session in get_db():
            try:
                service = PaymentProcessingService(
                    tx_repo=TransactionRepository(session),
                    fare_repo=FareBreakdownRepository(session),
                    pm_repo=PaymentMethodRepository(session),
                    earnings_repo=EarningsRepository(session),
                    rate_card_repo=RateCardRepository(session),
                    holiday_repo=HolidayRepository(session),
                    weather_repo=WeatherConditionRepository(session),
                    dialysis_repo=DialysisRatePlanRepository(session),
                    stripe_client=get_stripe_client(),
                    ride_client=RideServiceClient(settings.RIDE_SERVICE_URL),
                    publisher=get_publisher(),
                    service_type_repo=ServiceTypeConfigRepository(session),
                )

                refund_tx = await service.refund_ride_payment(
                    ride_id=payload.ride_id,
                    rider_id=payload.rider_id,
                )

                if refund_tx:
                    logger.info(
                        f"Ride {payload.ride_id} refund processed: ${float(refund_tx.amount)}"
                    )
                else:
                    logger.info(
                        f"Ride {payload.ride_id} cancelled - no payment to refund"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to process refund for ride {payload.ride_id}: {e}",
                    exc_info=True,
                )


async def setup_consumers() -> None:
    broker = get_broker()
    if not broker:
        logger.warning("Broker not available, skipping consumer setup")
        return

    ride_completed_consumer = RideCompletedConsumer(broker)
    await ride_completed_consumer.setup_queue(
        queue_name=Queues.PAYMENT_RIDE_COMPLETED,
        exchange_name=Exchanges.RIDES,
        routing_keys=[RoutingKeys.RIDE_COMPLETED],
    )

    ride_cancelled_consumer = RideCancelledConsumer(broker)
    await ride_cancelled_consumer.setup_queue(
        queue_name=Queues.PAYMENT_RIDE_CANCELLED,
        exchange_name=Exchanges.RIDES,
        routing_keys=[RoutingKeys.RIDE_CANCELLED],
    )

    logger.info("Payment service consumers initialized")
