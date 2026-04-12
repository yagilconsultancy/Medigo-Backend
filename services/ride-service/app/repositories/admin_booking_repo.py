from uuid import UUID

from sqlalchemy import String, cast, desc, extract, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recurring_ride import RecurringRide
from app.models.ride import Ride
from mediride_common.schemas.enums import RideStatus
from mediride_common.utils import utc_now

# Dashboard tab → DB status mapping
_STATUS_MAP = {
    "pending": [RideStatus.REQUESTED],
    "approved": [RideStatus.CONFIRMED],  # Approved but not yet assigned to driver
    "declined": [RideStatus.CANCELLED, RideStatus.NO_SHOW],
}


class AdminBookingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ==================== All Bookings ====================

    async def get_all_bookings(
        self,
        status_filter: str | None = None,
        ride_type_filter: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Ride], int]:
        conditions = [Ride.deleted_at.is_(None)]

        if status_filter and status_filter in _STATUS_MAP:
            conditions.append(Ride.status.in_(_STATUS_MAP[status_filter]))
        elif status_filter:
            conditions.append(Ride.status == status_filter)

        if ride_type_filter:
            conditions.append(Ride.ride_type == ride_type_filter)

        if search:
            pattern = f"%{search}%"
            conditions.append(
                or_(
                    Ride.pickup_address.ilike(pattern),
                    Ride.destination_address.ilike(pattern),
                    Ride.facility_name.ilike(pattern),
                )
            )

        base_query = select(Ride).where(*conditions)
        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            base_query.offset(offset).limit(limit).order_by(desc(Ride.created_at))
        )
        return list(result.scalars().all()), total

    # ==================== Pending Bookings ====================

    async def get_pending_bookings(
        self, offset: int = 0, limit: int = 20
    ) -> tuple[list[Ride], int]:
        conditions = [
            Ride.deleted_at.is_(None),
            Ride.status == RideStatus.REQUESTED,
        ]
        base_query = select(Ride).where(*conditions)
        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            base_query.offset(offset).limit(limit).order_by(Ride.created_at.asc())
        )
        return list(result.scalars().all()), total

    async def get_pending_kpis(self) -> dict:
        now = utc_now()

        # Pending count
        pending_result = await self.session.execute(
            select(func.count()).where(
                Ride.deleted_at.is_(None),
                Ride.status == RideStatus.REQUESTED,
            )
        )
        pending_now = pending_result.scalar_one()

        # Average wait time (minutes since created_at for REQUESTED rides)
        avg_wait_result = await self.session.execute(
            select(
                func.avg(extract("epoch", now - Ride.created_at) / 60)
            ).where(
                Ride.deleted_at.is_(None),
                Ride.status == RideStatus.REQUESTED,
            )
        )
        avg_wait_raw = avg_wait_result.scalar_one()
        avg_wait_minutes = round(avg_wait_raw) if avg_wait_raw else 0

        # Assigned count (CONFIRMED but not yet driver_assigned)
        assigned_result = await self.session.execute(
            select(func.count()).where(
                Ride.deleted_at.is_(None),
                Ride.status == RideStatus.CONFIRMED,
            )
        )
        assigned_count = assigned_result.scalar_one()

        return {
            "pending_now": pending_now,
            "avg_wait_minutes": avg_wait_minutes,
            "assigned_count": assigned_count,
        }

    # ==================== Scheduled Trips ====================

    async def get_scheduled_trips(
        self, offset: int = 0, limit: int = 20
    ) -> tuple[list[Ride], int]:
        now = utc_now()
        conditions = [
            Ride.deleted_at.is_(None),
            Ride.scheduled_at > now,
            Ride.status.notin_([
                RideStatus.CANCELLED,
                RideStatus.NO_SHOW,
                RideStatus.COMPLETED,
            ]),
        ]
        base_query = select(Ride).where(*conditions)
        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            base_query.offset(offset).limit(limit).order_by(Ride.scheduled_at.asc())
        )
        return list(result.scalars().all()), total

    async def get_scheduled_kpis(self) -> dict:
        now = utc_now()
        base_conditions = [
            Ride.deleted_at.is_(None),
            Ride.scheduled_at > now,
            Ride.status.notin_([
                RideStatus.CANCELLED,
                RideStatus.NO_SHOW,
                RideStatus.COMPLETED,
            ]),
        ]

        # Upcoming count
        upcoming_result = await self.session.execute(
            select(func.count()).where(*base_conditions)
        )
        upcoming_count = upcoming_result.scalar_one()

        # Recurring count
        recurring_result = await self.session.execute(
            select(func.count()).where(
                *base_conditions,
                Ride.recurring_ride_id.isnot(None),
            )
        )
        recurring_count = recurring_result.scalar_one()

        # Needs assignment (future rides without a driver)
        needs_assign_result = await self.session.execute(
            select(func.count()).where(
                *base_conditions,
                Ride.driver_id.is_(None),
            )
        )
        needs_assignment_count = needs_assign_result.scalar_one()

        return {
            "upcoming_count": upcoming_count,
            "recurring_count": recurring_count,
            "needs_assignment_count": needs_assignment_count,
        }

    # ==================== Cancelled Trips ====================

    async def get_cancelled_trips(
        self, offset: int = 0, limit: int = 20
    ) -> tuple[list[Ride], int]:
        conditions = [
            Ride.deleted_at.is_(None),
            Ride.status.in_([RideStatus.CANCELLED, RideStatus.NO_SHOW]),
        ]
        base_query = select(Ride).where(*conditions)
        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            base_query.offset(offset).limit(limit).order_by(desc(Ride.cancelled_at))
        )
        return list(result.scalars().all()), total

    async def get_cancelled_kpis(self) -> dict:
        # Total cancelled
        total_result = await self.session.execute(
            select(func.count()).where(
                Ride.deleted_at.is_(None),
                Ride.status.in_([RideStatus.CANCELLED, RideStatus.NO_SHOW]),
            )
        )
        total_cancelled = total_result.scalar_one()

        # No-show count
        noshow_result = await self.session.execute(
            select(func.count()).where(
                Ride.deleted_at.is_(None),
                Ride.status == RideStatus.NO_SHOW,
            )
        )
        no_show_count = noshow_result.scalar_one()

        return {
            "total_cancelled": total_cancelled,
            "no_show_count": no_show_count,
            "refunds_pending": 0,  # TODO: integrate with payment-service
            "refunds_processed": 0,
        }

    # ==================== Recurring Ride Lookup ====================

    async def get_recurring_ride(self, recurring_ride_id: UUID) -> RecurringRide | None:
        result = await self.session.execute(
            select(RecurringRide).where(RecurringRide.id == recurring_ride_id)
        )
        return result.scalar_one_or_none()
