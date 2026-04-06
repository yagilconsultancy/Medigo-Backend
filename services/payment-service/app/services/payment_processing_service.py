import logging
from uuid import UUID

from app.clients.stripe_client import StripeClient
from app.clients.ride_service_client import RideServiceClient
from app.models.transaction import Transaction
from app.repositories.dialysis_rate_plan_repo import DialysisRatePlanRepository
from app.repositories.earnings_repo import EarningsRepository
from app.repositories.fare_repo import FareBreakdownRepository
from app.repositories.holiday_repo import HolidayRepository
from app.repositories.payment_method_repo import PaymentMethodRepository
from app.repositories.rate_card_repo import RateCardRepository
from app.repositories.service_type_config_repo import ServiceTypeConfigRepository
from app.repositories.transaction_repo import TransactionRepository
from app.repositories.weather_condition_repo import WeatherConditionRepository
from app.services.fare_service import FareService
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher
from mediride_common.events.schemas import PaymentCompletedPayload
from mediride_common.exceptions import NotFoundError, ValidationError
from mediride_common.schemas.enums import PaymentStatus, TransactionType

logger = logging.getLogger(__name__)


class PaymentProcessingService:
    """Handles charging riders for completed rides via Stripe."""

    def __init__(
        self,
        tx_repo: TransactionRepository,
        fare_repo: FareBreakdownRepository,
        pm_repo: PaymentMethodRepository,
        earnings_repo: EarningsRepository,
        rate_card_repo: RateCardRepository,
        holiday_repo: HolidayRepository,
        weather_repo: WeatherConditionRepository,
        dialysis_repo: DialysisRatePlanRepository,
        stripe_client: StripeClient,
        ride_client: RideServiceClient,
        publisher: EventPublisher,
        service_type_repo: ServiceTypeConfigRepository | None = None,
    ):
        self.tx_repo = tx_repo
        self.fare_repo = fare_repo
        self.pm_repo = pm_repo
        self.earnings_repo = earnings_repo
        self.rate_card_repo = rate_card_repo
        self.holiday_repo = holiday_repo
        self.weather_repo = weather_repo
        self.dialysis_repo = dialysis_repo
        self.stripe = stripe_client
        self.ride_client = ride_client
        self.publisher = publisher
        self.service_type_repo = service_type_repo

    async def process_ride_payment(
        self,
        ride_id: UUID,
        rider_id: UUID,
        driver_id: UUID,
    ) -> Transaction:
        """Full ride payment flow: calculate fare -> charge rider -> record earnings."""

        # 1. Fetch ride details from ride-service
        ride_data = await self.ride_client.get_ride(ride_id)
        if not ride_data:
            raise NotFoundError(f"Ride {ride_id} not found in ride-service")

        # 2. Calculate fare
        fare_service = FareService(
            fare_repo=self.fare_repo,
            rate_card_repo=self.rate_card_repo,
            holiday_repo=self.holiday_repo,
            weather_repo=self.weather_repo,
            dialysis_repo=self.dialysis_repo,
            service_type_repo=self.service_type_repo,
        )
        breakdown = await fare_service.calculate_fare({
            "ride_id": ride_id,
            "ride_type": ride_data.get("ride_type", "ambulatory"),
            "trip_type": ride_data.get("trip_type", "transport_only"),
            "trip_structure": ride_data.get("trip_structure", "one_way"),
            "distance_miles": ride_data.get("actual_distance_miles",
                                            ride_data.get("estimated_distance_miles", 0)),
            "timeline": ride_data.get("timeline", []),
            "pickup_at": ride_data.get("pickup_at"),
            "scheduled_at": ride_data.get("scheduled_at"),
            "use_highway_407": ride_data.get("use_highway_407", False),
            "highway_407_route": ride_data.get("highway_407_route"),
            "is_dialysis_trip": ride_data.get("is_dialysis_trip", False),
            "pickup_address": ride_data.get("pickup_address", ""),
            "destination_address": ride_data.get("destination_address", ""),
            "pickup_city": ride_data.get("pickup_city", ""),
        })

        total_fare = float(breakdown.total_fare)
        driver_earnings = float(breakdown.driver_earnings)

        # 3. Find rider's default payment method
        rider_methods = await self.pm_repo.get_by_user(rider_id)
        default_pm = next(
            (m for m in rider_methods if m.is_default and m.external_id and m.stripe_customer_id),
            None,
        )

        if not default_pm:
            # No payment method on file - create a pending transaction
            logger.warning(f"No payment method for rider {rider_id} on ride {ride_id}")
            tx = Transaction(
                ride_id=ride_id,
                user_id=rider_id,
                transaction_type=TransactionType.RIDE_PAYMENT,
                amount=total_fare,
                status=PaymentStatus.PENDING,
                description=f"Ride payment pending - no payment method on file",
            )
            await self.tx_repo.create(tx)

            # Still record driver earnings (platform absorbs risk)
            await self._record_driver_earnings(ride_id, driver_id, driver_earnings)
            return tx

        # 4. Charge the rider via Stripe
        order_id = f"RIDE-{ride_id}"
        result = await self.stripe.purchase(
            order_id=order_id,
            amount=total_fare,
            data_key=default_pm.external_id,
            customer_id=default_pm.stripe_customer_id,
            description=f"MediRide #{str(ride_id)[:8]}",
        )

        if result.success:
            # Payment succeeded
            tx = Transaction(
                ride_id=ride_id,
                user_id=rider_id,
                transaction_type=TransactionType.RIDE_PAYMENT,
                amount=total_fare,
                status=PaymentStatus.COMPLETED,
                reference_id=result.transaction_id,
                description=f"Ride payment - Stripe ref: {result.reference_number}",
            )
            await self.tx_repo.create(tx)

            # Record driver earnings
            await self._record_driver_earnings(ride_id, driver_id, driver_earnings)

            # Update ride with final fare
            await self.ride_client.update_ride_fare(ride_id, total_fare)

            # Publish payment completed event
            await self.publisher.publish(
                Exchanges.PAYMENTS,
                RoutingKeys.PAYMENT_COMPLETED,
                PaymentCompletedPayload(
                    transaction_id=tx.id,
                    ride_id=ride_id,
                    user_id=rider_id,
                    amount=total_fare,
                    status=PaymentStatus.COMPLETED,
                ).model_dump(mode="json"),
            )

            logger.info(
                f"Ride {ride_id} payment of ${total_fare} charged to rider {rider_id} "
                f"(Stripe pi: {result.transaction_id})"
            )
        else:
            # Payment failed
            tx = Transaction(
                ride_id=ride_id,
                user_id=rider_id,
                transaction_type=TransactionType.RIDE_PAYMENT,
                amount=total_fare,
                status=PaymentStatus.FAILED,
                reference_id=result.response_code,
                description=f"Payment failed: {result.message}",
            )
            await self.tx_repo.create(tx)

            await self.publisher.publish(
                Exchanges.PAYMENTS,
                RoutingKeys.PAYMENT_FAILED,
                PaymentCompletedPayload(
                    transaction_id=tx.id,
                    ride_id=ride_id,
                    user_id=rider_id,
                    amount=total_fare,
                    status=PaymentStatus.FAILED,
                ).model_dump(mode="json"),
            )

            logger.error(
                f"Ride {ride_id} payment failed for rider {rider_id}: "
                f"{result.message} (code: {result.response_code})"
            )

            # Still record driver earnings even if rider payment fails
            await self._record_driver_earnings(ride_id, driver_id, driver_earnings)

        return tx

    async def refund_ride_payment(
        self, ride_id: UUID, rider_id: UUID
    ) -> Transaction | None:
        """Refund a completed ride payment via Stripe."""
        # Find the original completed payment transaction
        transactions = await self.tx_repo.get_by_ride_id(ride_id)
        original_tx = next(
            (t for t in transactions
             if t.transaction_type == TransactionType.RIDE_PAYMENT
             and t.status == PaymentStatus.COMPLETED
             and t.reference_id),
            None,
        )

        if not original_tx:
            logger.warning(f"No completed payment found for ride {ride_id} to refund")
            return None

        order_id = f"RIDE-{ride_id}"
        result = await self.stripe.refund(
            order_id=order_id,
            transaction_id=original_tx.reference_id,
            amount=float(original_tx.amount),
        )

        if result.success:
            refund_tx = Transaction(
                ride_id=ride_id,
                user_id=rider_id,
                transaction_type=TransactionType.REFUND,
                amount=float(original_tx.amount),
                status=PaymentStatus.COMPLETED,
                reference_id=result.transaction_id,
                description=f"Refund for ride {ride_id}",
            )
            await self.tx_repo.create(refund_tx)

            await self.publisher.publish(
                Exchanges.PAYMENTS,
                RoutingKeys.PAYMENT_REFUNDED,
                PaymentCompletedPayload(
                    transaction_id=refund_tx.id,
                    ride_id=ride_id,
                    user_id=rider_id,
                    amount=float(original_tx.amount),
                    status=PaymentStatus.REFUNDED,
                ).model_dump(mode="json"),
            )

            logger.info(f"Refund of ${original_tx.amount} processed for ride {ride_id}")
            return refund_tx
        else:
            logger.error(
                f"Refund failed for ride {ride_id}: {result.message}"
            )
            return None

    async def _record_driver_earnings(
        self, ride_id: UUID, driver_id: UUID, amount: float
    ) -> None:
        """Add earnings to driver balance and create a transaction record."""
        await self.earnings_repo.add_earnings(driver_id, amount)

        tx = Transaction(
            ride_id=ride_id,
            user_id=driver_id,
            transaction_type=TransactionType.RIDE_PAYMENT,
            amount=amount,
            status=PaymentStatus.COMPLETED,
            description=f"Earnings from ride {ride_id}",
        )
        await self.tx_repo.create(tx)

        logger.info(f"Recorded ${amount} earnings for driver {driver_id} from ride {ride_id}")
