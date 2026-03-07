import logging
from uuid import UUID

from app.dependencies import get_broker, get_db, get_publisher
from app.repositories.driver_repo import DriverRepository
from app.repositories.user_repo import UserRepository
from app.services.driver_service import DriverService
from app.services.user_service import UserService
from mediride_common.events.constants import Exchanges, Queues, RoutingKeys
from mediride_common.events.consumer import BaseEventConsumer
from mediride_common.events.schemas import EventEnvelope, RideRatingSubmittedPayload, UserRegisteredPayload
from mediride_common.schemas.enums import RatingType, UserRole

logger = logging.getLogger(__name__)


class UserRegisteredConsumer(BaseEventConsumer):
    """Consumes user.registered events to create user profiles."""

    async def handle(self, envelope: EventEnvelope) -> None:
        if envelope.event_type != RoutingKeys.USER_REGISTERED:
            return

        payload = UserRegisteredPayload(**envelope.payload)
        logger.info(f"Creating profile for user {payload.user_id}")

        # Get a database session
        async for session in get_db():
            user_repo = UserRepository(session)
            user_service = UserService(user_repo)

            # Check if profile already exists (idempotency)
            existing = await user_repo.get_by_id(payload.user_id)
            if existing:
                logger.info(f"Profile already exists for user {payload.user_id}")
                return

            await user_service.create_profile_from_registration(
                user_id=payload.user_id,
                email=payload.email,
                phone=payload.phone,
                role=payload.role,
                business_id=payload.business_id,
            )
            logger.info(f"Profile created for user {payload.user_id}")

            # If the user is a driver, also create driver profile
            if payload.role == UserRole.DRIVER and payload.business_id:
                driver_repo = DriverRepository(session)
                publisher = get_publisher()
                driver_service = DriverService(driver_repo, publisher)

                try:
                    await driver_service.create_driver_profile(
                        user_id=payload.user_id,
                        business_id=payload.business_id,
                        invited_via_email=payload.email,
                    )
                    logger.info(
                        f"Driver profile created for user {payload.user_id}, "
                        f"business {payload.business_id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to create driver profile for {payload.user_id}: {e}"
                    )


class RideRatingConsumer(BaseEventConsumer):
    """Consumes ride.rating.submitted events to update driver stats."""

    async def handle(self, envelope: EventEnvelope) -> None:
        if envelope.event_type != RoutingKeys.RIDE_RATING_SUBMITTED:
            return

        payload = RideRatingSubmittedPayload(**envelope.payload)

        # Only update driver stats for rider-to-driver ratings
        if payload.rating_type != RatingType.RIDER_TO_DRIVER:
            return

        logger.info(f"Updating driver {payload.rated_user_id} rating after ride {payload.ride_id}")

        async for session in get_db():
            driver_repo = DriverRepository(session)
            driver = await driver_repo.get_by_user_id(payload.rated_user_id)
            if not driver:
                logger.warning(f"Driver {payload.rated_user_id} not found for rating update")
                return

            # Update total trips and recalculate rating as running average
            new_total = driver.total_trips + 1
            current_rating = float(driver.rating)
            new_rating = round(
                (current_rating * driver.total_trips + payload.rating) / new_total, 2
            )

            await driver_repo.update(
                payload.rated_user_id,
                total_trips=new_total,
                rating=new_rating,
            )
            logger.info(
                f"Driver {payload.rated_user_id} stats updated: "
                f"trips={new_total}, rating={new_rating}"
            )


async def setup_consumers() -> None:
    """Set up all event consumers for the user service."""
    broker = get_broker()
    if not broker:
        logger.warning("Broker not available, skipping consumer setup")
        return

    consumer = UserRegisteredConsumer(broker)
    await consumer.setup_queue(
        queue_name=Queues.USER_SERVICE_USER_REGISTERED,
        exchange_name=Exchanges.AUTH,
        routing_keys=[RoutingKeys.USER_REGISTERED],
    )

    rating_consumer = RideRatingConsumer(broker)
    await rating_consumer.setup_queue(
        queue_name=Queues.USER_SERVICE_RATING_SUBMITTED,
        exchange_name=Exchanges.RIDES,
        routing_keys=[RoutingKeys.RIDE_RATING_SUBMITTED],
    )

    logger.info("User service consumers initialized")
