import asyncio
import logging
from uuid import UUID

from app.clients.payment_service_client import PaymentServiceClient
from app.clients.user_service_client import UserServiceClient
from app.models.admin_note import AdminNote
from app.models.ride import Ride
from app.models.ride_status_log import RideStatusLog
from app.repositories.admin_booking_repo import AdminBookingRepository
from app.repositories.admin_note_repo import AdminNoteRepository
from app.repositories.ride_repo import RideRepository
from app.repositories.status_log_repo import StatusLogRepository
from app.schemas.admin_booking import (
    AdminBookingDetailResponse,
    AdminNoteResponse,
    AvailableDriverResponse,
    CancelledTripResponse,
    CancelledTripsKPIs,
    FareBreakdownDetail,
    PendingBookingResponse,
    PendingBookingsKPIs,
    ScheduledTripResponse,
    ScheduledTripsKPIs,
    StatusLogEntry,
)
from app.services.ride_service import RideService
from app.services.ride_state_machine import VALID_TRANSITIONS
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.exceptions import NotFoundError, ValidationError
from mediride_common.schemas.enums import RideStatus
from mediride_common.utils import utc_now

logger = logging.getLogger(__name__)


class AdminBookingService:
    def __init__(
        self,
        booking_repo: AdminBookingRepository,
        note_repo: AdminNoteRepository,
        ride_repo: RideRepository,
        status_log_repo: StatusLogRepository,
        ride_service: RideService,
        user_client: UserServiceClient,
        payment_client: PaymentServiceClient,
    ):
        self.booking_repo = booking_repo
        self.note_repo = note_repo
        self.ride_repo = ride_repo
        self.status_log_repo = status_log_repo
        self.ride_service = ride_service
        self.user_client = user_client
        self.payment_client = payment_client
        # Access publisher through ride_service
        self.publisher = ride_service.publisher

    # ==================== All Bookings ====================

    async def get_all_bookings(
        self,
        status_filter: str | None,
        ride_type_filter: str | None,
        search: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[dict], int]:
        """Get all bookings with rider names enriched."""
        rides, total = await self.booking_repo.get_all_bookings(
            status_filter=status_filter,
            ride_type_filter=ride_type_filter,
            search=search,
            offset=offset,
            limit=limit,
        )

        # Batch fetch rider names
        rider_ids = [r.rider_id for r in rides]
        rider_details = {}
        if rider_ids:
            try:
                riders_data = await self.user_client.batch_get_users(rider_ids)
                rider_details = {
                    UUID(u["id"]): f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
                    for u in riders_data if u.get("id")
                }
            except Exception as e:
                logger.error(f"Failed to fetch rider names: {e}")

        # Enrich rides with rider names
        enriched_rides = []
        for ride in rides:
            ride_dict = {
                "id": ride.id,
                "rider_id": ride.rider_id,
                "driver_id": ride.driver_id,
                "caregiver_id": ride.caregiver_id,
                "business_id": ride.business_id,
                "ride_type": ride.ride_type,
                "trip_type": ride.trip_type,
                "trip_structure": ride.trip_structure,
                "pickup_address": ride.pickup_address,
                "destination_address": ride.destination_address,
                "scheduled_at": ride.scheduled_at,
                "status": ride.status,
                "estimated_distance_miles": ride.estimated_distance_miles,
                "estimated_duration_minutes": ride.estimated_duration_minutes,
                "estimated_fare": ride.estimated_fare,
                "final_fare": ride.final_fare,
                "special_instructions": ride.special_instructions,
                "visit_type": ride.visit_type,
                "facility_name": ride.facility_name,
                "booking_channel": ride.booking_channel,
                "facility_id": ride.facility_id,
                "use_highway_407": ride.use_highway_407,
                "highway_407_route": ride.highway_407_route,
                "is_dialysis_trip": ride.is_dialysis_trip,
                "created_at": ride.created_at,
                "rider_name": rider_details.get(ride.rider_id, f"Rider {str(ride.rider_id)[:8]}"),
            }
            enriched_rides.append(ride_dict)

        return enriched_rides, total

    # ==================== Pending Bookings ====================

    async def get_pending_bookings(
        self, offset: int, limit: int
    ) -> tuple[list[PendingBookingResponse], int]:
        rides, total = await self.booking_repo.get_pending_bookings(offset, limit)
        now = utc_now()

        # Enrich with rider info (HTTP calls can run concurrently)
        async def _enrich(ride: Ride) -> PendingBookingResponse:
            profile = await self.user_client.get_user_profile(ride.rider_id)
            rider_name = "Unknown"
            rider_phone = None
            if profile:
                rider_name = (
                    f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip()
                    or "Unknown"
                )
                rider_phone = profile.get("phone")

            wait_minutes = int((now - ride.created_at).total_seconds() / 60)
            return PendingBookingResponse(
                id=ride.id,
                rider_id=ride.rider_id,
                rider_name=rider_name,
                rider_phone=rider_phone,
                ride_type=ride.ride_type,
                trip_type=ride.trip_type,
                trip_structure=ride.trip_structure,
                pickup_address=ride.pickup_address,
                destination_address=ride.destination_address,
                scheduled_at=ride.scheduled_at,
                created_at=ride.created_at,
                wait_minutes=wait_minutes,
                special_instructions=ride.special_instructions,
                mobility_level=ride.mobility_level,
                assistance_level=ride.assistance_level,
                recurring_ride_id=ride.recurring_ride_id,
                is_recurring=ride.recurring_ride_id is not None,
            )

        enriched = await asyncio.gather(*[_enrich(r) for r in rides])
        return list(enriched), total

    async def get_pending_kpis(self) -> PendingBookingsKPIs:
        data = await self.booking_repo.get_pending_kpis()
        return PendingBookingsKPIs(**data)

    # ==================== Scheduled Trips ====================

    async def get_scheduled_trips(
        self, offset: int, limit: int
    ) -> tuple[list[ScheduledTripResponse], int]:
        rides, total = await self.booking_repo.get_scheduled_trips(offset, limit)

        # Enrich with rider/driver names (HTTP calls can run concurrently)
        async def _enrich(ride: Ride) -> ScheduledTripResponse:
            rider_profile, driver_profile = await asyncio.gather(
                self.user_client.get_user_profile(ride.rider_id),
                self.user_client.get_driver_profile(ride.driver_id) if ride.driver_id else _none(),
            )

            rider_name = _extract_name(rider_profile)
            driver_name = _extract_name(driver_profile) if driver_profile else None

            # Fetch recurring ride info if applicable
            recurring_days = None
            recurring_frequency = None
            if ride.recurring_ride_id:
                rec = await self.booking_repo.get_recurring_ride(ride.recurring_ride_id)
                if rec:
                    recurring_days = rec.days_of_week
                    recurring_frequency = rec.frequency

            return ScheduledTripResponse(
                id=ride.id,
                rider_id=ride.rider_id,
                rider_name=rider_name,
                ride_type=ride.ride_type,
                trip_type=ride.trip_type,
                pickup_address=ride.pickup_address,
                destination_address=ride.destination_address,
                scheduled_at=ride.scheduled_at,
                status=ride.status,
                driver_id=ride.driver_id,
                driver_name=driver_name,
                recurring_ride_id=ride.recurring_ride_id,
                is_recurring=ride.recurring_ride_id is not None,
                recurring_days=recurring_days,
                recurring_frequency=recurring_frequency,
            )

        enriched = await asyncio.gather(*[_enrich(r) for r in rides])
        return list(enriched), total

    async def get_scheduled_kpis(self) -> ScheduledTripsKPIs:
        data = await self.booking_repo.get_scheduled_kpis()
        return ScheduledTripsKPIs(**data)

    # ==================== Cancelled Trips ====================

    async def get_cancelled_trips(
        self, offset: int, limit: int
    ) -> tuple[list[CancelledTripResponse], int]:
        rides, total = await self.booking_repo.get_cancelled_trips(offset, limit)

        async def _enrich(ride: Ride) -> CancelledTripResponse:
            rider_profile, driver_profile, cancelled_by_profile = await asyncio.gather(
                self.user_client.get_user_profile(ride.rider_id),
                self.user_client.get_driver_profile(ride.driver_id) if ride.driver_id else _none(),
                self.user_client.get_user_profile(ride.cancelled_by) if ride.cancelled_by else _none(),
            )

            return CancelledTripResponse(
                id=ride.id,
                rider_id=ride.rider_id,
                rider_name=_extract_name(rider_profile),
                pickup_address=ride.pickup_address,
                destination_address=ride.destination_address,
                scheduled_at=ride.scheduled_at,
                cancelled_at=ride.cancelled_at,
                cancellation_reason=ride.cancellation_reason,
                cancelled_by=ride.cancelled_by,
                cancelled_by_name=_extract_name(cancelled_by_profile) if cancelled_by_profile else None,
                status=ride.status,
                driver_id=ride.driver_id,
                driver_name=_extract_name(driver_profile) if driver_profile else None,
                final_fare=float(ride.final_fare) if ride.final_fare else None,
            )

        enriched = await asyncio.gather(*[_enrich(r) for r in rides])
        return list(enriched), total

    async def get_cancelled_kpis(self) -> CancelledTripsKPIs:
        data = await self.booking_repo.get_cancelled_kpis()
        return CancelledTripsKPIs(**data)

    # ==================== Booking Detail ====================

    async def get_booking_detail(self, ride_id: UUID) -> AdminBookingDetailResponse:
        ride = await self.ride_repo.get_by_id(ride_id)
        if not ride:
            raise NotFoundError("Booking not found")

        # Fetch admin notes (DB query — sequential)
        notes = await self.note_repo.get_by_ride(ride_id)

        # Fetch external data concurrently (HTTP calls)
        rider_profile, driver_profile, caregiver_profile, fare_data = await asyncio.gather(
            self.user_client.get_user_profile(ride.rider_id),
            self.user_client.get_driver_profile(ride.driver_id) if ride.driver_id else _none(),
            self.user_client.get_driver_profile(ride.caregiver_id) if ride.caregiver_id else _none(),
            self.payment_client.get_fare_breakdown(ride_id) if ride.status == RideStatus.COMPLETED else _none(),
        )

        # Build rider info
        rider_name = _extract_name(rider_profile)
        rider_phone = rider_profile.get("phone") if rider_profile else None
        rider_rating = float(rider_profile.get("rating", 5.0)) if rider_profile else 5.0
        rider_trip_count = rider_profile.get("total_trips", 0) if rider_profile else 0

        # Build driver info
        driver_name = None
        driver_phone = None
        driver_rating = None
        driver_vehicle = {}
        if driver_profile:
            driver_name = _extract_name(driver_profile)
            driver_phone = driver_profile.get("phone")
            driver_rating = float(driver_profile.get("rating", 5.0))
            # Vehicle fields are returned at the top level of the profile.
            driver_vehicle = driver_profile

        # Build caregiver info
        caregiver_name = _extract_name(caregiver_profile) if caregiver_profile else None

        # Build timeline
        timeline = [
            StatusLogEntry(
                from_status=log.from_status,
                to_status=log.to_status,
                timestamp=log.timestamp,
                notes=log.notes,
                changed_by=log.changed_by,
            )
            for log in sorted(ride.status_logs, key=lambda l: l.timestamp)
        ]

        # Build admin notes
        admin_notes_resp = [
            AdminNoteResponse(
                id=n.id,
                ride_id=n.ride_id,
                author_id=n.author_id,
                author_type=n.author_type,
                content=n.content,
                created_at=n.created_at,
            )
            for n in notes
        ]

        # Build fare breakdown
        fare_breakdown = None
        if fare_data:
            fare_breakdown = FareBreakdownDetail(
                base_fare=fare_data.get("base_fare"),
                distance_charge=fare_data.get("distance_charge"),
                wait_time_charge=fare_data.get("wait_time_charge"),
                surcharges_capped=fare_data.get("surcharges_capped"),
                highway_407_toll=fare_data.get("highway_407_toll"),
                insurance_gateway_fee=fare_data.get("insurance_gateway_fee"),
                total_fare=fare_data.get("total_fare"),
                driver_earnings=fare_data.get("driver_earnings"),
            )

        return AdminBookingDetailResponse(
            id=ride.id,
            rider_id=ride.rider_id,
            driver_id=ride.driver_id,
            caregiver_id=ride.caregiver_id,
            business_id=ride.business_id,
            ride_type=ride.ride_type,
            trip_type=ride.trip_type,
            trip_structure=ride.trip_structure,
            status=ride.status,
            pickup_address=ride.pickup_address,
            pickup_latitude=float(ride.pickup_latitude) if ride.pickup_latitude else None,
            pickup_longitude=float(ride.pickup_longitude) if ride.pickup_longitude else None,
            destination_address=ride.destination_address,
            destination_latitude=float(ride.destination_latitude) if ride.destination_latitude else None,
            destination_longitude=float(ride.destination_longitude) if ride.destination_longitude else None,
            scheduled_at=ride.scheduled_at,
            pickup_at=ride.pickup_at,
            dropoff_at=ride.dropoff_at,
            created_at=ride.created_at,
            estimated_distance_miles=float(ride.estimated_distance_miles) if ride.estimated_distance_miles else None,
            actual_distance_miles=float(ride.actual_distance_miles) if ride.actual_distance_miles else None,
            estimated_duration_minutes=ride.estimated_duration_minutes,
            actual_duration_minutes=ride.actual_duration_minutes,
            estimated_fare=float(ride.estimated_fare) if ride.estimated_fare else None,
            final_fare=float(ride.final_fare) if ride.final_fare else None,
            special_instructions=ride.special_instructions,
            mobility_level=ride.mobility_level,
            assistance_level=ride.assistance_level,
            visit_type=ride.visit_type,
            facility_name=ride.facility_name,
            appointment_time=ride.appointment_time,
            passenger_first_name=ride.passenger_first_name,
            passenger_last_name=ride.passenger_last_name,
            passenger_phone=ride.passenger_phone,
            cancellation_reason=ride.cancellation_reason,
            cancelled_at=ride.cancelled_at,
            cancelled_by=ride.cancelled_by,
            use_highway_407=ride.use_highway_407,
            is_dialysis_trip=ride.is_dialysis_trip,
            rider_name=rider_name,
            rider_phone=rider_phone,
            rider_rating=rider_rating,
            rider_trip_count=rider_trip_count,
            caregiver_name=caregiver_name,
            driver_name=driver_name,
            driver_phone=driver_phone,
            driver_rating=driver_rating,
            driver_vehicle_type=driver_vehicle.get("vehicle_type"),
            driver_vehicle_make=driver_vehicle.get("vehicle_make"),
            driver_vehicle_model=driver_vehicle.get("vehicle_model"),
            driver_vehicle_plate=driver_vehicle.get("vehicle_plate"),
            driver_vehicle_color=driver_vehicle.get("vehicle_color"),
            timeline=timeline,
            admin_notes=admin_notes_resp,
            fare_breakdown=fare_breakdown,
            recurring_ride_id=ride.recurring_ride_id,
            is_recurring=ride.recurring_ride_id is not None,
            allowed_status_transitions=list(VALID_TRANSITIONS.get(ride.status, [])),
        )

    # ==================== Approve / Decline ====================

    async def approve_booking(
        self, ride_id: UUID, admin_id: UUID, notes: str | None = None
    ) -> Ride:
        ride = await self.ride_service.transition_status(
            ride_id=ride_id,
            to_status=RideStatus.CONFIRMED,
            changed_by=admin_id,
            notes=notes or "Booking approved by admin",
        )
        # Auto-create system note
        await self._create_system_note(
            ride_id, admin_id, "Booking approved by admin"
        )
        return ride

    async def decline_booking(
        self, ride_id: UUID, admin_id: UUID, reason: str
    ) -> Ride:
        # Truncate reason for ride column (50 char limit)
        truncated_reason = reason[:50] if len(reason) > 50 else reason
        ride = await self.ride_service.cancel_ride(
            ride_id=ride_id,
            cancelled_by=admin_id,
            reason=truncated_reason,
        )
        # Store full reason in admin note
        await self._create_system_note(
            ride_id, admin_id, f"Booking declined: {reason}"
        )
        return ride

    # ==================== Edit Booking ====================

    # Bookings can only be edited before they are in transit or finished.
    NON_EDITABLE_STATUSES = {
        RideStatus.IN_PROGRESS,
        RideStatus.COMPLETED,
        RideStatus.CANCELLED,
        RideStatus.NO_SHOW,
    }

    async def update_booking(
        self, ride_id: UUID, admin_id: UUID, updates: dict
    ) -> Ride:
        """Edit a booking's trip and medical details.

        Only fields present in ``updates`` are changed. Editing is rejected
        once the ride is in progress or in a terminal state.
        """
        ride = await self.ride_repo.get_by_id(ride_id)
        if ride is None:
            raise NotFoundError("Booking not found")

        if ride.status in self.NON_EDITABLE_STATUSES:
            raise ValidationError(
                f"Booking cannot be edited while status is '{ride.status}'"
            )

        # Drop keys that were not provided (None) so we never null out columns.
        clean_updates = {k: v for k, v in updates.items() if v is not None}
        if not clean_updates:
            return ride

        await self.ride_repo.update(ride_id, **clean_updates)

        changed_keys = sorted(clean_updates.keys())
        await self._create_system_note(
            ride_id, admin_id, f"Booking edited by admin. Fields: {', '.join(changed_keys)}"
        )

        # Notify the rider that their booking details changed.
        await self.publisher.publish(
            Exchanges.RIDES,
            RoutingKeys.RIDE_UPDATED,
            {
                "ride_id": str(ride_id),
                "rider_id": str(ride.rider_id),
                "updated_by": str(admin_id),
                "changed_fields": changed_keys,
            },
        )

        updated = await self.ride_repo.get_by_id(ride_id)
        return updated or ride

    # ==================== Change Status ====================

    async def change_status(
        self, ride_id: UUID, admin_id: UUID, to_status: str, notes: str | None = None
    ) -> Ride:
        """Admin-driven status change.

        Goes through the ride state machine, so only valid transitions are
        accepted and the matching rider notification/event is published.
        """
        ride = await self.ride_service.transition_status(
            ride_id=ride_id,
            to_status=to_status,
            changed_by=admin_id,
            notes=notes or f"Status changed to {to_status} by admin",
        )
        await self._create_system_note(
            ride_id, admin_id, f"Status changed to '{to_status}' by admin"
        )
        return ride

    # ==================== Assign / Reassign Driver ====================

    async def assign_driver(
        self, ride_id: UUID, driver_id: UUID, admin_id: UUID
    ) -> Ride:
        return await self.ride_service.admin_assign_driver(
            ride_id=ride_id,
            driver_id=driver_id,
            admin_id=admin_id,
        )

    async def assign_caregiver(
        self, ride_id: UUID, caregiver_id: UUID, admin_id: UUID
    ) -> Ride:
        ride = await self.ride_service.admin_assign_caregiver(
            ride_id=ride_id,
            caregiver_id=caregiver_id,
            admin_id=admin_id,
        )
        await self._create_system_note(
            ride_id, admin_id, f"Caregiver assigned: {caregiver_id}"
        )
        return ride

    async def reassign_driver(
        self, ride_id: UUID, new_driver_id: UUID, admin_id: UUID, reason: str | None = None
    ) -> Ride:
        ride = await self.ride_repo.get_by_id(ride_id)
        if not ride:
            raise NotFoundError("Booking not found")

        reassignable = [
            RideStatus.DRIVER_ASSIGNED,
            RideStatus.DRIVER_EN_ROUTE,
            RideStatus.DRIVER_ARRIVED,
        ]
        if ride.status not in reassignable:
            raise ValidationError(
                f"Cannot reassign driver when ride is in '{ride.status}' status"
            )

        # Validate new driver
        driver_profile = await self.user_client.get_driver_profile(new_driver_id)
        if not driver_profile:
            raise ValidationError("Driver not found or not approved")

        old_driver_id = ride.driver_id
        old_driver_profile = (
            await self.user_client.get_driver_profile(old_driver_id)
            if old_driver_id else None
        )
        old_driver_name = _display_name(old_driver_profile, old_driver_id)
        new_driver_name = _display_name(driver_profile, new_driver_id)
        await self.ride_repo.update(ride_id, driver_id=new_driver_id)

        # Publish event to free old driver
        if old_driver_id:
            await self.publisher.publish(
                Exchanges.RIDES,
                RoutingKeys.RIDE_DRIVER_UNASSIGNED,
                {
                    "ride_id": str(ride_id),
                    "driver_id": str(old_driver_id),
                    "reason": "driver_reassigned",
                    "reassigned_to": str(new_driver_id),
                    "reassigned_by": str(admin_id),
                },
            )

        # Publish event to assign new driver
        await self.publisher.publish(
            Exchanges.RIDES,
            RoutingKeys.RIDE_DRIVER_ASSIGNED,
            {
                "ride_id": str(ride_id),
                "driver_id": str(new_driver_id),
                "assigned_by": str(admin_id),
                "assigned_via": "reassignment",
                "previous_driver": str(old_driver_id) if old_driver_id else None,
            },
        )

        # Log the reassignment
        log = RideStatusLog(
            ride_id=ride_id,
            from_status=ride.status,
            to_status=ride.status,
            changed_by=admin_id,
            notes=f"Driver reassigned: {old_driver_name} → {new_driver_name}",
        )
        await self.status_log_repo.create(log)

        # Admin note
        note_text = f"Driver reassigned from {old_driver_name} to {new_driver_name}"
        if reason:
            note_text += f": {reason}"
        await self._create_system_note(ride_id, admin_id, note_text)

        # Return updated ride
        return await self.ride_repo.get_by_id(ride_id)

    async def cancel_trip(
        self, ride_id: UUID, admin_id: UUID, reason: str
    ) -> Ride:
        truncated_reason = reason[:50] if len(reason) > 50 else reason
        ride = await self.ride_service.cancel_ride(
            ride_id=ride_id,
            cancelled_by=admin_id,
            reason=truncated_reason,
        )
        await self._create_system_note(
            ride_id, admin_id, f"Trip cancelled by admin: {reason}"
        )
        return ride

    # ==================== Available Drivers ====================

    async def get_available_drivers(self, ride_id: UUID) -> list[AvailableDriverResponse]:
        ride = await self.ride_repo.get_by_id(ride_id)
        if not ride:
            raise NotFoundError("Booking not found")

        drivers = await self.user_client.get_available_drivers()

        return [
            AvailableDriverResponse(
                driver_id=d.get("id") or d.get("driver_id") or d.get("user_id"),
                name=f"{d.get('first_name', '')} {d.get('last_name', '')}".strip() or "Unknown",
                phone=d.get("phone"),
                avatar_url=d.get("avatar_url"),
                rating=float(d.get("rating", 5.0)),
                vehicle_type=d.get("vehicle_type") or (d.get("vehicle", {}) or {}).get("vehicle_type"),
                vehicle_make=d.get("vehicle_make") or (d.get("vehicle", {}) or {}).get("make"),
                vehicle_model=d.get("vehicle_model") or (d.get("vehicle", {}) or {}).get("model"),
                vehicle_plate=d.get("vehicle_plate") or (d.get("vehicle", {}) or {}).get("plate"),
            )
            for d in drivers
            if d.get("id") or d.get("driver_id") or d.get("user_id")
        ]

    # ==================== Admin Notes ====================

    async def add_note(
        self, ride_id: UUID, admin_id: UUID, content: str, author_type: str = "admin"
    ) -> AdminNoteResponse:
        # Verify ride exists
        ride = await self.ride_repo.get_by_id(ride_id)
        if not ride:
            raise NotFoundError("Booking not found")

        note = AdminNote(
            ride_id=ride_id,
            author_id=admin_id,
            author_type=author_type,
            content=content,
        )
        note = await self.note_repo.create(note)
        return AdminNoteResponse(
            id=note.id,
            ride_id=note.ride_id,
            author_id=note.author_id,
            author_type=note.author_type,
            content=note.content,
            created_at=note.created_at,
        )

    async def get_notes(self, ride_id: UUID) -> list[AdminNoteResponse]:
        ride = await self.ride_repo.get_by_id(ride_id)
        if not ride:
            raise NotFoundError("Booking not found")

        notes = await self.note_repo.get_by_ride(ride_id)
        return [
            AdminNoteResponse(
                id=n.id,
                ride_id=n.ride_id,
                author_id=n.author_id,
                author_type=n.author_type,
                content=n.content,
                created_at=n.created_at,
            )
            for n in notes
        ]

    # ==================== Helpers ====================

    async def _create_system_note(
        self, ride_id: UUID, admin_id: UUID, content: str
    ) -> AdminNote:
        note = AdminNote(
            ride_id=ride_id,
            author_id=admin_id,
            author_type="system",
            content=content,
        )
        return await self.note_repo.create(note)


async def _none():
    """Helper coroutine that returns None (for asyncio.gather)."""
    return None


def _extract_name(profile: dict | None) -> str:
    if not profile:
        return "Unknown"
    return (
        f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip()
        or "Unknown"
    )


def _display_name(profile: dict | None, user_id: UUID | None) -> str:
    name = _extract_name(profile)
    if name != "Unknown":
        return name
    return str(user_id) if user_id else "Unknown"
