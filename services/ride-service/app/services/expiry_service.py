"""Background task to expire stale business assignments."""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.ride_repo import RideRepository
from app.repositories.status_log_repo import StatusLogRepository
from app.services.ride_state_machine import validate_transition
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher
from mediride_common.events.schemas import RideBusinessResponsePayload
from mediride_common.schemas.enums import RideStatus
from mediride_common.utils import utc_now

logger = logging.getLogger(__name__)


async def expire_stale_business_assignments(
    session_factory: async_sessionmaker[AsyncSession],
    publisher: EventPublisher,
) -> int:
    """Find PENDING_BUSINESS_ASSIGNMENT rides past expiry and return them to REQUESTED.

    Returns the number of expired rides processed.
    """
    expired_count = 0

    async with session_factory() as session:
        try:
            ride_repo = RideRepository(session)
            status_log_repo = StatusLogRepository(session)

            expired_rides = await ride_repo.get_expired_business_assignments()

            for ride in expired_rides:
                validate_transition(ride.status, RideStatus.REQUESTED)

                old_business_id = ride.assigned_to_business_id

                # Clear assignment fields
                await ride_repo.update(
                    ride.id,
                    status=RideStatus.REQUESTED,
                    assigned_to_business_id=None,
                    assigned_by_admin_id=None,
                    assigned_to_business_at=None,
                    business_accepted_at=None,
                    business_assignment_expires_at=None,
                )

                # Log the status transition
                from app.models.ride_status_log import RideStatusLog

                log = RideStatusLog(
                    ride_id=ride.id,
                    from_status=RideStatus.PENDING_BUSINESS_ASSIGNMENT,
                    to_status=RideStatus.REQUESTED,
                    changed_by=None,
                    note="Business assignment expired",
                )
                await status_log_repo.create(log)

                # Publish expiry event
                await publisher.publish(
                    exchange=Exchanges.RIDES,
                    routing_key=RoutingKeys.RIDE_BUSINESS_ASSIGNMENT_EXPIRED,
                    payload=RideBusinessResponsePayload(
                        ride_id=ride.id,
                        rider_id=ride.rider_id,
                        business_id=old_business_id,
                        reason="Business assignment expired",
                    ).model_dump(mode="json"),
                )

                expired_count += 1
                logger.info(
                    f"Expired business assignment for ride {ride.id} "
                    f"(business {old_business_id})"
                )

            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Error expiring stale business assignments")

    return expired_count


async def run_expiry_loop(
    session_factory: async_sessionmaker[AsyncSession],
    publisher: EventPublisher,
    interval_seconds: int = 60,
) -> None:
    """Periodically check for and expire stale business assignments."""
    logger.info(
        f"Starting business assignment expiry loop (interval={interval_seconds}s)"
    )
    while True:
        try:
            count = await expire_stale_business_assignments(session_factory, publisher)
            if count > 0:
                logger.info(f"Expired {count} stale business assignment(s)")
        except Exception:
            logger.exception("Unhandled error in expiry loop")
        await asyncio.sleep(interval_seconds)
