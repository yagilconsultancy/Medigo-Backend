import logging
import secrets
from uuid import UUID

from app.clients.payment_service_client import PaymentServiceClient
from app.clients.user_service_client import UserServiceClient
from app.config import settings
from app.models.ride import Ride
from app.models.ride_rating import RideRating
from app.models.ride_status_log import RideStatusLog
from app.models.recurring_ride import RecurringRide
from app.repositories.rating_repo import RatingRepository
from app.repositories.recurring_ride_repo import RecurringRideRepository
from app.repositories.ride_repo import RideRepository
from app.repositories.ride_request_repo import RideRequestRepository
from app.repositories.status_log_repo import StatusLogRepository
from app.services.ride_state_machine import get_routing_key_for_status, validate_transition
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher
from mediride_common.events.schemas import (
    RideCreatedPayload,
    RideRatingSubmittedPayload,
    RideStatusChangedPayload,
)
from mediride_common.exceptions import NotFoundError, ValidationError
from mediride_common.schemas.enums import RatingType, RideStatus, TripType
from mediride_common.utils import normalize_to_utc, utc_now

logger = logging.getLogger(__name__)


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


class RideService:
    def __init__(
        self,
        ride_repo: RideRepository,
        request_repo: RideRequestRepository,
        status_log_repo: StatusLogRepository,
        rating_repo: RatingRepository,
        recurring_ride_repo: RecurringRideRepository,
        publisher: EventPublisher,
        user_client: UserServiceClient,
        payment_client: PaymentServiceClient | None = None,
    ):
        self.ride_repo = ride_repo
        self.request_repo = request_repo
        self.status_log_repo = status_log_repo
        self.rating_repo = rating_repo
        self.recurring_ride_repo = recurring_ride_repo
        self.publisher = publisher
        self.user_client = user_client
        self.payment_client = payment_client or PaymentServiceClient(
            settings.PAYMENT_SERVICE_URL
        )

    async def _populate_estimates(self, ride_data: dict) -> dict:
        """Compute ride estimates server-side to avoid trusting caller defaults."""
        estimate = await self.payment_client.estimate_ride(
            pickup_address=ride_data["pickup_address"],
            destination_address=ride_data["destination_address"],
            pickup_latitude=ride_data.get("pickup_latitude"),
            pickup_longitude=ride_data.get("pickup_longitude"),
            destination_latitude=ride_data.get("destination_latitude"),
            destination_longitude=ride_data.get("destination_longitude"),
            scheduled_at=ride_data["scheduled_at"].isoformat(),
            ride_type=_enum_value(ride_data["ride_type"]),
            trip_type=_enum_value(ride_data.get("trip_type", TripType.TRANSPORT_ONLY)),
            trip_structure=_enum_value(ride_data.get("trip_structure", "one_way")),
            use_highway_407=ride_data.get("use_highway_407", False),
            highway_407_route=ride_data.get("highway_407_route"),
            is_dialysis_trip=ride_data.get("is_dialysis_trip", False),
        )
        if not estimate:
            logger.warning(
                "Using caller-provided ride estimates because payment-service estimate failed "
                "for %s -> %s",
                ride_data["pickup_address"],
                ride_data["destination_address"],
            )
            return ride_data

        ride_data["estimated_distance_miles"] = estimate.get("distance_miles")
        duration_minutes = estimate.get("duration_minutes")
        ride_data["estimated_duration_minutes"] = (
            int(round(duration_minutes)) if duration_minutes is not None else None
        )
        ride_data["estimated_fare"] = estimate.get("total_fare")
        return ride_data

    # ---- Core Ride Operations ----

    async def create_ride(self, rider_id: UUID, **ride_data) -> Ride:
        if ride_data.get("scheduled_at"):
            ride_data["scheduled_at"] = normalize_to_utc(
                ride_data["scheduled_at"],
                settings.DEFAULT_TIMEZONE,
            )
        if ride_data.get("appointment_time"):
            ride_data["appointment_time"] = normalize_to_utc(
                ride_data["appointment_time"],
                settings.DEFAULT_TIMEZONE,
            )

        # Validate: TRANSPORT_CARE_ASSISTANT requires a future scheduled ride
        trip_type = ride_data.get("trip_type", TripType.TRANSPORT_ONLY)
        if trip_type == TripType.TRANSPORT_CARE_ASSISTANT:
            scheduled_at = ride_data.get("scheduled_at")
            if not scheduled_at or scheduled_at <= utc_now():
                raise ValidationError(
                    "Transport + Care Assistant rides must be scheduled in the future "
                    "(care assistant needs advance notice)"
                )

        if ride_data.get("guest_session_id"):
            ride_data.setdefault("booking_channel", "website_guest")
            ride_data.setdefault("share_token", secrets.token_urlsafe(32))

        ride_data = await self._populate_estimates(ride_data)
        ride = Ride(rider_id=rider_id, **ride_data)
        ride = await self.ride_repo.create(ride)

        # Log initial status
        log = RideStatusLog(
            ride_id=ride.id,
            from_status=None,
            to_status=RideStatus.REQUESTED,
            changed_by=rider_id,
        )
        await self.status_log_repo.create(log)

        await self.publisher.publish(
            Exchanges.RIDES,
            RoutingKeys.RIDE_CREATED,
            RideCreatedPayload(
                ride_id=ride.id,
                rider_id=rider_id,
                ride_type=ride.ride_type,
                pickup_address=ride.pickup_address,
                destination_address=ride.destination_address,
                scheduled_at=ride.scheduled_at,
                estimated_cost=float(ride.estimated_fare) if ride.estimated_fare else None,
            ).model_dump(mode="json"),
        )

        return ride

    async def get_ride(self, ride_id: UUID) -> Ride:
        ride = await self.ride_repo.get_by_id(ride_id)
        if not ride:
            raise NotFoundError("Ride not found")
        return ride

    async def get_ride_detail(self, ride_id: UUID) -> dict:
        ride = await self.get_ride(ride_id)

        # Enrich with rider info
        rider_info = await self.user_client.get_user_profile(ride.rider_id)
        rider_name = "Unknown"
        rider_rating = 5.0
        rider_trip_count = 0
        if rider_info:
            first = rider_info.get("first_name", "")
            last = rider_info.get("last_name", "")
            rider_name = f"{first} {last}".strip() or "Unknown"
            rider_rating = rider_info.get("rating", 5.0)
            rider_trip_count = rider_info.get("total_trips", 0)

        # Get ratings
        driver_rating = await self.rating_repo.get_by_ride_and_type(
            ride_id, RatingType.RIDER_TO_DRIVER
        )
        rider_rating_given = await self.rating_repo.get_by_ride_and_type(
            ride_id, RatingType.DRIVER_TO_RIDER
        )

        # Get timeline
        timeline = await self.status_log_repo.get_by_ride(ride_id)

        return {
            "ride": ride,
            "rider_name": rider_name,
            "rider_rating": rider_rating,
            "rider_trip_count": rider_trip_count,
            "driver_rating": driver_rating,
            "rider_rating_given": rider_rating_given,
            "timeline": timeline,
        }

    # ---- Status Transitions ----

    async def transition_status(
        self, ride_id: UUID, to_status: str, changed_by: UUID | None,
        notes: str | None = None
    ) -> Ride:
        ride = await self.get_ride(ride_id)
        validate_transition(ride.status, to_status)

        update_data: dict = {"status": to_status}

        # Handle specific status transitions
        if to_status == RideStatus.IN_PROGRESS:
            update_data["pickup_at"] = utc_now()
        elif to_status == RideStatus.COMPLETED:
            update_data["dropoff_at"] = utc_now()
            if ride.pickup_at:
                delta = utc_now() - ride.pickup_at
                update_data["actual_duration_minutes"] = int(delta.total_seconds() / 60)

        await self.ride_repo.update(ride_id, **update_data)

        log = RideStatusLog(
            ride_id=ride_id,
            from_status=ride.status,
            to_status=to_status,
            changed_by=changed_by,
            notes=notes,
        )
        await self.status_log_repo.create(log)

        routing_key = get_routing_key_for_status(to_status)
        if routing_key:
            await self.publisher.publish(
                Exchanges.RIDES,
                routing_key,
                RideStatusChangedPayload(
                    ride_id=ride_id,
                    rider_id=ride.rider_id,
                    driver_id=ride.driver_id,
                    from_status=ride.status,
                    to_status=to_status,
                    changed_by=changed_by,
                ).model_dump(mode="json"),
            )

        return await self.ride_repo.get_by_id(ride_id)

    async def cancel_ride(
        self, ride_id: UUID, cancelled_by: UUID, reason: str
    ) -> Ride:
        ride = await self.get_ride(ride_id)
        validate_transition(ride.status, RideStatus.CANCELLED)

        await self.ride_repo.update(
            ride_id,
            status=RideStatus.CANCELLED,
            cancelled_by=cancelled_by,
            cancellation_reason=reason,
            cancelled_at=utc_now(),
        )

        log = RideStatusLog(
            ride_id=ride_id,
            from_status=ride.status,
            to_status=RideStatus.CANCELLED,
            changed_by=cancelled_by,
            notes=f"Cancelled: {reason}",
        )
        await self.status_log_repo.create(log)

        await self.publisher.publish(
            Exchanges.RIDES,
            RoutingKeys.RIDE_CANCELLED,
            RideStatusChangedPayload(
                ride_id=ride_id,
                rider_id=ride.rider_id,
                driver_id=ride.driver_id,
                from_status=ride.status,
                to_status=RideStatus.CANCELLED,
                changed_by=cancelled_by,
            ).model_dump(mode="json"),
        )

        return await self.ride_repo.get_by_id(ride_id)

    # ---- Admin Assignment ----

    async def admin_assign_driver(
        self, ride_id: UUID, driver_id: UUID, admin_id: UUID
    ) -> Ride:
        ride = await self.get_ride(ride_id)

        if ride.status not in (RideStatus.REQUESTED, RideStatus.CONFIRMED):
            raise ValidationError(
                f"Can only assign driver in REQUESTED or CONFIRMED status. "
                f"Current: {ride.status}"
            )

        # Validate driver exists and is approved
        driver_info = await self.user_client.get_driver_profile(driver_id)
        if not driver_info:
            raise NotFoundError("Driver not found")
        if not driver_info.get("is_approved"):
            raise ValidationError("Driver is not approved")

        # One-step: REQUESTED → CONFIRMED → DRIVER_ASSIGNED
        if ride.status == RideStatus.REQUESTED:
            await self.transition_status(
                ride_id, RideStatus.CONFIRMED, admin_id,
                notes="Admin confirmed for direct assignment"
            )

        await self.ride_repo.update(ride_id, driver_id=driver_id)
        driver_name = _extract_name(driver_info)
        await self.transition_status(
            ride_id, RideStatus.DRIVER_ASSIGNED, admin_id,
            notes=f"Admin assigned driver {driver_name}"
        )

        return await self.ride_repo.get_by_id(ride_id)

    async def admin_assign_caregiver(
        self, ride_id: UUID, caregiver_id: UUID, admin_id: UUID
    ) -> Ride:
        """
        Assign a caregiver (care assistant) to a ride.

        Only permitted when:
          - trip_type is TRANSPORT_CARE_ASSISTANT
          - scheduled_at is strictly in the future (not an instant ride)
          - ride status is REQUESTED or CONFIRMED
          - the caregiver exists, is approved, and has a `specialty` set
        """
        ride = await self.get_ride(ride_id)

        # Only TRANSPORT_CARE_ASSISTANT rides support caregivers
        if ride.trip_type != TripType.TRANSPORT_CARE_ASSISTANT:
            raise ValidationError(
                "Caregivers can only be assigned to Transport + Care Assistant rides"
            )

        # Must be a scheduled (future) ride — not instant
        if not ride.scheduled_at or ride.scheduled_at <= utc_now():
            raise ValidationError(
                "Caregivers can only be assigned to scheduled (future) rides"
            )

        if ride.status not in (RideStatus.REQUESTED, RideStatus.CONFIRMED):
            raise ValidationError(
                f"Can only assign caregiver in REQUESTED or CONFIRMED status. "
                f"Current: {ride.status}"
            )

        # Validate caregiver exists and has a specialty (= is a caregiver)
        caregiver_info = await self.user_client.get_driver_profile(caregiver_id)
        if not caregiver_info:
            raise NotFoundError("Caregiver not found")
        if not caregiver_info.get("is_approved"):
            raise ValidationError("Caregiver is not approved")
        if not caregiver_info.get("specialty"):
            raise ValidationError(
                "Selected user is not a caregiver (no specialty set)"
            )

        await self.ride_repo.update(ride_id, caregiver_id=caregiver_id)

        # Log the caregiver assignment as a status-log note, but keep the ride
        # in its current state (driver assignment is tracked separately).
        log = RideStatusLog(
            ride_id=ride_id,
            from_status=ride.status,
            to_status=ride.status,
            changed_by=admin_id,
            notes=f"Admin assigned caregiver {_extract_name(caregiver_info)}",
        )
        await self.status_log_repo.create(log)

        return await self.ride_repo.get_by_id(ride_id)

    # ---- Admin Queries ----

    async def get_pending_admin_rides(
        self, offset: int = 0, limit: int = 20
    ) -> tuple[list[Ride], int]:
        return await self.ride_repo.get_pending_admin_review(offset, limit)

    async def get_all_rides_admin(
        self, status_filter: str | None = None,
        ride_type_filter: str | None = None,
        offset: int = 0, limit: int = 20
    ) -> tuple[list[Ride], int]:
        return await self.ride_repo.get_all_rides_admin(
            status_filter, ride_type_filter, offset, limit
        )

    # ---- Driver Queries ----

    async def get_upcoming_rides_for_driver(
        self, driver_id: UUID, offset: int = 0, limit: int = 20
    ) -> tuple[list[Ride], int]:
        return await self.ride_repo.get_upcoming_by_driver(driver_id, offset, limit)

    async def get_driver_trips(
        self, driver_id: UUID, status_filter: str | None = None,
        offset: int = 0, limit: int = 20
    ) -> tuple[list[Ride], int]:
        return await self.ride_repo.get_by_driver(driver_id, status_filter, offset, limit)

    async def get_driver_stats(self, driver_id: UUID) -> dict:
        stats = await self.ride_repo.get_driver_stats(driver_id)
        avg_rating = await self.rating_repo.get_average_rating(driver_id)
        stats["rating"] = round(avg_rating, 2)

        # Today's earnings
        now = utc_now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        stats["earnings_today"] = await self.ride_repo.get_driver_earnings_today(
            driver_id, today_start
        )
        return stats

    # ---- Rider Queries ----

    async def get_rider_trips(
        self, rider_id: UUID, status_filter: str | None = None,
        offset: int = 0, limit: int = 20
    ) -> tuple[list[Ride], int]:
        return await self.ride_repo.get_by_rider(rider_id, status_filter, offset, limit)

    async def get_active_ride_for_rider(self, rider_id: UUID) -> Ride | None:
        """Get rider's current active ride (confirmed, assigned, en route, arrived, or in progress)."""
        return await self.ride_repo.get_active_ride_for_rider(rider_id)

    async def get_active_ride_for_driver(self, driver_id: UUID) -> Ride | None:
        """Get driver's current active ride (confirmed, assigned, en route, arrived, or in progress)."""
        return await self.ride_repo.get_active_ride_for_driver(driver_id)

    # ---- Ratings ----

    async def submit_rating(
        self, ride_id: UUID, rated_by: UUID, rating: int,
        comment: str | None, rating_type: str
    ) -> RideRating:
        ride = await self.get_ride(ride_id)
        if ride.status != RideStatus.COMPLETED:
            raise ValidationError("Can only rate completed rides")

        # Determine who is being rated
        if rating_type == RatingType.DRIVER_TO_RIDER:
            if ride.driver_id != rated_by:
                raise ValidationError("Only the assigned driver can rate the rider")
            rated_user_id = ride.rider_id
        elif rating_type == RatingType.RIDER_TO_DRIVER:
            if ride.rider_id != rated_by:
                raise ValidationError("Only the rider can rate the driver")
            if not ride.driver_id:
                raise ValidationError("No driver assigned to this ride")
            rated_user_id = ride.driver_id
        else:
            raise ValidationError(f"Invalid rating type: {rating_type}")

        existing = await self.rating_repo.get_by_ride_and_type(ride_id, rating_type)
        if existing:
            raise ValidationError("Rating already submitted for this ride")

        ride_rating = RideRating(
            ride_id=ride_id,
            rated_user_id=rated_user_id,
            rated_by_user_id=rated_by,
            rating_type=rating_type,
            rating=rating,
            comment=comment,
        )
        ride_rating = await self.rating_repo.create(ride_rating)

        await self.publisher.publish(
            Exchanges.RIDES,
            RoutingKeys.RIDE_RATING_SUBMITTED,
            RideRatingSubmittedPayload(
                ride_id=ride_id,
                rated_user_id=rated_user_id,
                rated_by_user_id=rated_by,
                rating=rating,
                rating_type=rating_type,
            ).model_dump(mode="json"),
        )

        return ride_rating

    async def get_ride_ratings(self, ride_id: UUID) -> list[RideRating]:
        return await self.rating_repo.get_ratings_for_ride(ride_id)

    # ---- Timeline ----

    async def get_ride_timeline(self, ride_id: UUID) -> list[RideStatusLog]:
        await self.get_ride(ride_id)  # verify exists
        return await self.status_log_repo.get_by_ride(ride_id)

    # ---- Recurring Rides ----

    async def create_recurring_ride(self, rider_id: UUID, **data) -> RecurringRide:
        recurring = RecurringRide(rider_id=rider_id, **data)
        return await self.recurring_ride_repo.create(recurring)

    async def get_recurring_rides(self, rider_id: UUID) -> list[RecurringRide]:
        return await self.recurring_ride_repo.get_active_by_rider(rider_id)

    async def deactivate_recurring_ride(self, rec_id: UUID, rider_id: UUID) -> None:
        recurring = await self.recurring_ride_repo.get_by_id(rec_id)
        if not recurring:
            raise NotFoundError("Recurring ride not found")
        if recurring.rider_id != rider_id:
            raise ValidationError("Not your recurring ride")
        await self.recurring_ride_repo.deactivate(rec_id)

    # ---- Rebook ----

    async def rebook_ride(self, ride_id: UUID, rider_id: UUID, scheduled_at) -> Ride:
        """Clone a completed/cancelled ride into a new booking."""
        original = await self.get_ride(ride_id)
        if original.rider_id != rider_id:
            raise ValidationError("Not your ride")

        scheduled_at = normalize_to_utc(scheduled_at, settings.DEFAULT_TIMEZONE)

        new_ride_data = await self._populate_estimates(
            {
                "business_id": original.business_id,
                "ride_type": original.ride_type,
                "trip_type": original.trip_type,
                "trip_structure": original.trip_structure,
                "pickup_address": original.pickup_address,
                "pickup_latitude": original.pickup_latitude,
                "pickup_longitude": original.pickup_longitude,
                "destination_address": original.destination_address,
                "destination_latitude": original.destination_latitude,
                "destination_longitude": original.destination_longitude,
                "scheduled_at": scheduled_at,
                "visit_type": original.visit_type,
                "facility_name": original.facility_name,
                "special_instructions": original.special_instructions,
                "passenger_id": original.passenger_id,
                "mobility_level": original.mobility_level,
                "assistance_level": original.assistance_level,
                "use_highway_407": original.use_highway_407,
                "highway_407_route": original.highway_407_route,
                "is_dialysis_trip": original.is_dialysis_trip,
                "estimated_distance_miles": original.estimated_distance_miles,
                "estimated_duration_minutes": original.estimated_duration_minutes,
                "estimated_fare": original.estimated_fare,
            }
        )

        new_ride = Ride(
            rider_id=rider_id,
            **new_ride_data,
        )
        new_ride = await self.ride_repo.create(new_ride)

        log = RideStatusLog(
            ride_id=new_ride.id,
            from_status=None,
            to_status=RideStatus.REQUESTED,
            changed_by=rider_id,
            notes="Rebooked from ride " + str(ride_id),
        )
        await self.status_log_repo.create(log)

        await self.publisher.publish(
            Exchanges.RIDES,
            RoutingKeys.RIDE_CREATED,
            RideCreatedPayload(
                ride_id=new_ride.id,
                rider_id=rider_id,
                ride_type=new_ride.ride_type,
                pickup_address=new_ride.pickup_address,
                destination_address=new_ride.destination_address,
                scheduled_at=new_ride.scheduled_at,
                estimated_cost=float(new_ride.estimated_fare) if new_ride.estimated_fare else None,
            ).model_dump(mode="json"),
        )

        return new_ride

    # ---- Share ----

    async def share_ride(self, ride_id: UUID, rider_id: UUID) -> str:
        """Generate a share token for a ride, returns the token."""
        ride = await self.get_ride(ride_id)
        if ride.rider_id != rider_id:
            raise ValidationError("Not your ride")

        if ride.share_token:
            return ride.share_token

        token = secrets.token_urlsafe(32)
        await self.ride_repo.update(ride_id, share_token=token)
        return token

    async def get_ride_by_share_token(self, token: str) -> Ride:
        ride = await self.ride_repo.get_by_share_token(token)
        if not ride:
            raise NotFoundError("Shared ride not found")
        return ride

    # ---- Contact Driver ----

    async def get_driver_contact(self, ride_id: UUID, rider_id: UUID) -> dict:
        """Get assigned driver contact info for a ride."""
        ride = await self.get_ride(ride_id)
        if ride.rider_id != rider_id:
            raise ValidationError("Not your ride")
        if not ride.driver_id:
            raise ValidationError("No driver assigned to this ride yet")

        driver_info = await self.user_client.get_driver_profile(ride.driver_id)
        if not driver_info:
            raise NotFoundError("Driver profile not found")

        return {
            "driver_id": str(ride.driver_id),
            "first_name": driver_info.get("first_name", ""),
            "last_name": driver_info.get("last_name", ""),
            "phone": driver_info.get("phone"),
            "avatar_url": driver_info.get("avatar_url"),
            "rating": driver_info.get("rating", 5.0),
            "vehicle_type": driver_info.get("vehicle_type"),
            "vehicle_make": driver_info.get("vehicle_make"),
            "vehicle_model": driver_info.get("vehicle_model"),
            "vehicle_plate": driver_info.get("vehicle_plate"),
            "vehicle_color": driver_info.get("vehicle_color"),
        }


def _extract_name(profile: dict | None) -> str:
    if not profile:
        return "Unknown"
    return (
        f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip()
        or "Unknown"
    )
