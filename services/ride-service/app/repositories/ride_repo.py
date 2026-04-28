from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import Numeric, case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ride import Ride
from mediride_common.schemas.enums import RideStatus
from mediride_common.utils import utc_now


ACTIVE_RIDE_STATUSES = [
    RideStatus.CONFIRMED,
    RideStatus.DRIVER_ASSIGNED,
    RideStatus.DRIVER_EN_ROUTE,
    RideStatus.DRIVER_ARRIVED,
    RideStatus.IN_PROGRESS,
]

ACTIVE_RIDE_STATUS_PRIORITY = {
    RideStatus.IN_PROGRESS: 5,
    RideStatus.DRIVER_ARRIVED: 4,
    RideStatus.DRIVER_EN_ROUTE: 3,
    RideStatus.DRIVER_ASSIGNED: 2,
    RideStatus.CONFIRMED: 1,
}


def _active_ride_priority_order():
    return case(
        *(
            (Ride.status == status, priority)
            for status, priority in ACTIVE_RIDE_STATUS_PRIORITY.items()
        ),
        else_=0,
    ).desc()


class RideRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, ride: Ride) -> Ride:
        self.session.add(ride)
        await self.session.flush()
        return ride

    async def get_by_id(self, ride_id: UUID) -> Ride | None:
        result = await self.session.execute(
            select(Ride).where(Ride.id == ride_id, Ride.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def update(self, ride_id: UUID, **kwargs) -> None:
        await self.session.execute(
            update(Ride).where(Ride.id == ride_id).values(**kwargs)
        )

    async def get_upcoming_by_driver(
        self, driver_id: UUID, offset: int = 0, limit: int = 20
    ) -> tuple[list[Ride], int]:
        base_query = select(Ride).where(
            Ride.driver_id == driver_id,
            Ride.deleted_at.is_(None),
            Ride.status.in_([
                RideStatus.CONFIRMED,
                RideStatus.DRIVER_ASSIGNED,
                RideStatus.DRIVER_EN_ROUTE,
                RideStatus.DRIVER_ARRIVED,
                RideStatus.IN_PROGRESS,
            ]),
        )
        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            base_query.offset(offset).limit(limit).order_by(Ride.scheduled_at.asc())
        )
        return list(result.scalars().all()), total

    async def get_by_driver(
        self,
        driver_id: UUID,
        status_filter: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Ride], int]:
        conditions = [Ride.driver_id == driver_id, Ride.deleted_at.is_(None)]

        if status_filter == "upcoming":
            conditions.append(Ride.status.in_([
                RideStatus.CONFIRMED,
                RideStatus.DRIVER_ASSIGNED, RideStatus.DRIVER_EN_ROUTE,
                RideStatus.DRIVER_ARRIVED, RideStatus.IN_PROGRESS,
            ]))
        elif status_filter == "completed":
            conditions.append(Ride.status == RideStatus.COMPLETED)
        elif status_filter == "cancelled":
            conditions.append(Ride.status.in_([RideStatus.CANCELLED, RideStatus.NO_SHOW]))
        elif status_filter:
            conditions.append(Ride.status == status_filter)

        base_query = select(Ride).where(*conditions)

        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            base_query.offset(offset).limit(limit).order_by(Ride.scheduled_at.desc())
        )
        return list(result.scalars().all()), total

    async def get_by_rider(
        self,
        rider_id: UUID,
        status_filter: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Ride], int]:
        conditions = [Ride.rider_id == rider_id, Ride.deleted_at.is_(None)]

        if status_filter == "upcoming":
            conditions.append(Ride.status.in_([
                RideStatus.REQUESTED,
                RideStatus.CONFIRMED, RideStatus.DRIVER_ASSIGNED,
                RideStatus.DRIVER_EN_ROUTE, RideStatus.DRIVER_ARRIVED,
                RideStatus.IN_PROGRESS,
            ]))
        elif status_filter == "completed":
            conditions.append(Ride.status == RideStatus.COMPLETED)
        elif status_filter == "cancelled":
            conditions.append(Ride.status.in_([RideStatus.CANCELLED, RideStatus.NO_SHOW]))
        elif status_filter:
            conditions.append(Ride.status == status_filter)

        base_query = select(Ride).where(*conditions)

        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            base_query.offset(offset).limit(limit).order_by(Ride.scheduled_at.desc())
        )
        return list(result.scalars().all()), total

    async def get_by_share_token(self, share_token: str) -> Ride | None:
        result = await self.session.execute(
            select(Ride).where(Ride.share_token == share_token, Ride.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_guest_session_and_ride_id(
        self, guest_session_id: UUID, ride_id: UUID
    ) -> Ride | None:
        result = await self.session.execute(
            select(Ride).where(
                Ride.id == ride_id,
                Ride.guest_session_id == guest_session_id,
                Ride.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_latest_by_guest_session(self, guest_session_id: UUID) -> Ride | None:
        result = await self.session.execute(
            select(Ride)
            .where(
                Ride.guest_session_id == guest_session_id,
                Ride.deleted_at.is_(None),
            )
            .order_by(
                _active_ride_priority_order(),
                Ride.scheduled_at.desc(),
                Ride.created_at.desc(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_driver_stats(self, driver_id: UUID) -> dict:
        completed_count = await self.session.execute(
            select(func.count()).where(
                Ride.driver_id == driver_id,
                Ride.status == RideStatus.COMPLETED,
                Ride.deleted_at.is_(None),
            )
        )
        total_trips = completed_count.scalar_one()

        avg_result = await self.session.execute(
            select(func.avg(Ride.final_fare)).where(
                Ride.driver_id == driver_id,
                Ride.status == RideStatus.COMPLETED,
                Ride.final_fare.isnot(None),
                Ride.deleted_at.is_(None),
            )
        )
        avg_fare = avg_result.scalar_one() or 0

        duration_result = await self.session.execute(
            select(func.sum(Ride.actual_duration_minutes)).where(
                Ride.driver_id == driver_id,
                Ride.status == RideStatus.COMPLETED,
                Ride.actual_duration_minutes.isnot(None),
                Ride.deleted_at.is_(None),
            )
        )
        total_minutes = duration_result.scalar_one() or 0

        return {
            "total_trips": total_trips,
            "hours_online": round(float(total_minutes) / 60, 1),
            "average_earnings": round(float(avg_fare), 2),
        }

    async def get_driver_rides_in_period(
        self, driver_id: UUID, start: datetime, end: datetime
    ) -> list[Ride]:
        result = await self.session.execute(
            select(Ride).where(
                Ride.driver_id == driver_id,
                Ride.status == RideStatus.COMPLETED,
                Ride.dropoff_at >= start,
                Ride.dropoff_at <= end,
                Ride.deleted_at.is_(None),
            ).order_by(Ride.dropoff_at.desc())
        )
        return list(result.scalars().all())

    async def get_driver_earnings_today(self, driver_id: UUID, today_start: datetime) -> float:
        result = await self.session.execute(
            select(func.coalesce(func.sum(Ride.final_fare), 0)).where(
                Ride.driver_id == driver_id,
                Ride.status == RideStatus.COMPLETED,
                Ride.dropoff_at >= today_start,
                Ride.deleted_at.is_(None),
            )
        )
        return float(result.scalar_one())

    # ---- Admin Queries ----

    async def get_pending_admin_review(
        self, offset: int = 0, limit: int = 20
    ) -> tuple[list[Ride], int]:
        base_query = select(Ride).where(
            Ride.status == RideStatus.REQUESTED,
            Ride.deleted_at.is_(None),
        )
        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            base_query.offset(offset).limit(limit).order_by(Ride.created_at.asc())
        )
        return list(result.scalars().all()), total

    async def get_all_rides_admin(
        self,
        status_filter: str | None = None,
        ride_type_filter: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Ride], int]:
        conditions = [Ride.deleted_at.is_(None)]
        if status_filter:
            conditions.append(Ride.status == status_filter)
        if ride_type_filter:
            conditions.append(Ride.ride_type == ride_type_filter)

        base_query = select(Ride).where(*conditions)
        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            base_query.offset(offset).limit(limit).order_by(Ride.created_at.desc())
        )
        return list(result.scalars().all()), total

    async def get_active_transit_rides(self) -> list[Ride]:
        """Get all rides in active transit states for admin monitoring."""
        result = await self.session.execute(
            select(Ride).where(
                Ride.status.in_([
                    RideStatus.DRIVER_ASSIGNED,
                    RideStatus.DRIVER_EN_ROUTE,
                    RideStatus.DRIVER_ARRIVED,
                    RideStatus.IN_PROGRESS,
                ]),
                Ride.deleted_at.is_(None),
            ).order_by(Ride.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_active_ride_for_rider(self, rider_id: UUID) -> Ride | None:
        """Get rider's current active ride (not cancelled, completed, or no-show)."""
        result = await self.session.execute(
            select(Ride).where(
                Ride.rider_id == rider_id,
                Ride.status.in_(ACTIVE_RIDE_STATUSES),
                Ride.deleted_at.is_(None),
            )
            .order_by(
                _active_ride_priority_order(),
                Ride.scheduled_at.desc(),
                Ride.created_at.desc(),
            )
            .limit(1)
        )
        return result.scalars().first()

    async def get_active_ride_for_driver(self, driver_id: UUID) -> Ride | None:
        """Get driver's current active ride (not cancelled, completed, or no-show)."""
        result = await self.session.execute(
            select(Ride).where(
                Ride.driver_id == driver_id,
                Ride.status.in_(ACTIVE_RIDE_STATUSES),
                Ride.deleted_at.is_(None),
            )
            .order_by(
                _active_ride_priority_order(),
                Ride.scheduled_at.desc(),
                Ride.created_at.desc(),
            )
            .limit(1)
        )
        return result.scalars().first()

    async def get_completed_today_count(self) -> int:
        """Count rides completed today (since midnight UTC)."""
        today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await self.session.execute(
            select(func.count()).where(
                Ride.status == RideStatus.COMPLETED,
                Ride.dropoff_at >= today_start,
                Ride.deleted_at.is_(None),
            )
        )
        return result.scalar_one()

    # ---- Rider Queries (for admin rider management) ----

    async def get_rider_stats(self, rider_id: UUID) -> dict:
        completed_count = await self.session.execute(
            select(func.count()).where(
                Ride.rider_id == rider_id,
                Ride.status == RideStatus.COMPLETED,
                Ride.deleted_at.is_(None),
            )
        )
        total_trips = completed_count.scalar_one()

        spent_result = await self.session.execute(
            select(func.coalesce(func.sum(Ride.final_fare), 0)).where(
                Ride.rider_id == rider_id,
                Ride.status == RideStatus.COMPLETED,
                Ride.final_fare.isnot(None),
                Ride.deleted_at.is_(None),
            )
        )
        total_spent = float(spent_result.scalar_one())

        avg_result = await self.session.execute(
            select(func.avg(Ride.final_fare)).where(
                Ride.rider_id == rider_id,
                Ride.status == RideStatus.COMPLETED,
                Ride.final_fare.isnot(None),
                Ride.deleted_at.is_(None),
            )
        )
        avg_cost = float(avg_result.scalar_one() or 0)

        last_ride_result = await self.session.execute(
            select(func.max(Ride.dropoff_at)).where(
                Ride.rider_id == rider_id,
                Ride.status == RideStatus.COMPLETED,
                Ride.deleted_at.is_(None),
            )
        )
        last_ride_date = last_ride_result.scalar_one()

        first_ride_result = await self.session.execute(
            select(func.min(Ride.created_at)).where(
                Ride.rider_id == rider_id,
                Ride.deleted_at.is_(None),
            )
        )
        first_ride_date = first_ride_result.scalar_one()

        return {
            "total_trips": total_trips,
            "total_spent": round(total_spent, 2),
            "avg_cost": round(avg_cost, 2),
            "last_ride_date": last_ride_date.isoformat() if last_ride_date else None,
            "first_ride_date": first_ride_date.isoformat() if first_ride_date else None,
        }

    async def get_rider_completed_rides(
        self, rider_id: UUID, offset: int = 0, limit: int = 20
    ) -> tuple[list[Ride], int]:
        base_query = select(Ride).where(
            Ride.rider_id == rider_id,
            Ride.status == RideStatus.COMPLETED,
            Ride.deleted_at.is_(None),
        )
        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            base_query.order_by(Ride.dropoff_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def get_batch_rider_activity(self, rider_ids: list[UUID]) -> dict:
        if not rider_ids:
            return {}

        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        prev_month_end = current_month_start - timedelta(seconds=1)
        prev_month_start = prev_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        base_conditions = [
            Ride.rider_id.in_(rider_ids),
            Ride.status == RideStatus.COMPLETED,
            Ride.deleted_at.is_(None),
        ]

        # Last ride date per rider
        last_ride_result = await self.session.execute(
            select(Ride.rider_id, func.max(Ride.dropoff_at).label("last_ride"))
            .where(*base_conditions)
            .group_by(Ride.rider_id)
        )
        last_rides = {row.rider_id: row.last_ride for row in last_ride_result.all()}

        # Trips in last 7 days
        trips_7d_result = await self.session.execute(
            select(Ride.rider_id, func.count().label("cnt"))
            .where(*base_conditions, Ride.dropoff_at >= seven_days_ago)
            .group_by(Ride.rider_id)
        )
        trips_7d = {row.rider_id: row.cnt for row in trips_7d_result.all()}

        # Trips in last 30 days
        trips_30d_result = await self.session.execute(
            select(Ride.rider_id, func.count().label("cnt"))
            .where(*base_conditions, Ride.dropoff_at >= thirty_days_ago)
            .group_by(Ride.rider_id)
        )
        trips_30d = {row.rider_id: row.cnt for row in trips_30d_result.all()}

        # Trips current month
        trips_cm_result = await self.session.execute(
            select(Ride.rider_id, func.count().label("cnt"))
            .where(*base_conditions, Ride.dropoff_at >= current_month_start)
            .group_by(Ride.rider_id)
        )
        trips_cm = {row.rider_id: row.cnt for row in trips_cm_result.all()}

        # Trips previous month
        trips_pm_result = await self.session.execute(
            select(Ride.rider_id, func.count().label("cnt"))
            .where(
                *base_conditions,
                Ride.dropoff_at >= prev_month_start,
                Ride.dropoff_at <= prev_month_end,
            )
            .group_by(Ride.rider_id)
        )
        trips_pm = {row.rider_id: row.cnt for row in trips_pm_result.all()}

        result = {}
        for rid in rider_ids:
            last_ride = last_rides.get(rid)
            result[str(rid)] = {
                "last_ride_date": last_ride.isoformat() if last_ride else None,
                "trips_last_7d": trips_7d.get(rid, 0),
                "trips_last_30d": trips_30d.get(rid, 0),
                "trips_current_month": trips_cm.get(rid, 0),
                "trips_prev_month": trips_pm.get(rid, 0),
            }
        return result
