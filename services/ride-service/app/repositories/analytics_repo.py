from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import Date, String, case, cast, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ride import Ride
from app.models.ride_rating import RideRating
from app.models.ride_status_log import RideStatusLog
from mediride_common.schemas.enums import RideStatus
from mediride_common.utils import utc_now


class AnalyticsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---- KPI helpers ----

    async def get_trip_count(
        self, since: datetime | None = None, business_id: UUID | None = None
    ) -> int:
        conditions = [Ride.deleted_at.is_(None)]
        if since:
            conditions.append(Ride.created_at >= since)
        if business_id:
            conditions.append(Ride.assigned_to_business_id == business_id)
        result = await self.session.execute(
            select(func.count()).where(*conditions)
        )
        return result.scalar_one()

    async def get_completed_trip_count(
        self, since: datetime | None = None, business_id: UUID | None = None
    ) -> int:
        conditions = [
            Ride.deleted_at.is_(None),
            Ride.status == RideStatus.COMPLETED,
        ]
        if since:
            conditions.append(Ride.dropoff_at >= since)
        if business_id:
            conditions.append(Ride.assigned_to_business_id == business_id)
        result = await self.session.execute(
            select(func.count()).where(*conditions)
        )
        return result.scalar_one()

    async def get_active_driver_count(
        self, since: datetime, business_id: UUID | None = None
    ) -> int:
        conditions = [
            Ride.deleted_at.is_(None),
            Ride.driver_id.isnot(None),
            Ride.status.in_([
                RideStatus.DRIVER_ASSIGNED,
                RideStatus.DRIVER_EN_ROUTE,
                RideStatus.DRIVER_ARRIVED,
                RideStatus.IN_PROGRESS,
                RideStatus.COMPLETED,
            ]),
            Ride.updated_at >= since,
        ]
        if business_id:
            conditions.append(Ride.assigned_to_business_id == business_id)
        result = await self.session.execute(
            select(func.count(func.distinct(Ride.driver_id))).where(*conditions)
        )
        return result.scalar_one()

    async def get_pending_booking_count(
        self, business_id: UUID | None = None
    ) -> int:
        conditions = [
            Ride.deleted_at.is_(None),
            Ride.status.in_([
                RideStatus.REQUESTED,
                RideStatus.PENDING_BUSINESS_ASSIGNMENT,
            ]),
        ]
        if business_id:
            conditions.append(Ride.assigned_to_business_id == business_id)
        result = await self.session.execute(
            select(func.count()).where(*conditions)
        )
        return result.scalar_one()

    async def get_revenue(
        self, since: datetime | None = None, business_id: UUID | None = None
    ) -> float:
        conditions = [
            Ride.deleted_at.is_(None),
            Ride.status == RideStatus.COMPLETED,
            Ride.final_fare.isnot(None),
        ]
        if since:
            conditions.append(Ride.dropoff_at >= since)
        if business_id:
            conditions.append(Ride.assigned_to_business_id == business_id)
        result = await self.session.execute(
            select(func.coalesce(func.sum(Ride.final_fare), 0)).where(*conditions)
        )
        return float(result.scalar_one())

    # ---- Trip Volume Trend ----

    async def get_trip_volume_trend(
        self, days: int, business_id: UUID | None = None
    ) -> list[dict]:
        now = utc_now()
        since = now - timedelta(days=days)
        conditions = [
            Ride.deleted_at.is_(None),
            Ride.created_at >= since,
        ]
        if business_id:
            conditions.append(Ride.assigned_to_business_id == business_id)

        date_col = cast(Ride.created_at, Date).label("ride_date")
        result = await self.session.execute(
            select(date_col, func.count().label("count"))
            .where(*conditions)
            .group_by(date_col)
            .order_by(date_col)
        )
        return [{"date": row.ride_date, "count": row.count} for row in result.all()]

    # ---- Trip Status Distribution ----

    async def get_status_distribution(
        self, business_id: UUID | None = None
    ) -> list[dict]:
        conditions = [Ride.deleted_at.is_(None)]
        if business_id:
            conditions.append(Ride.assigned_to_business_id == business_id)

        # Map granular statuses to display groups
        display_status = case(
            (Ride.status == RideStatus.COMPLETED, "Completed"),
            (Ride.status.in_([
                RideStatus.DRIVER_ASSIGNED,
                RideStatus.CONFIRMED,
                RideStatus.PENDING_BUSINESS_ASSIGNMENT,
            ]), "Assigned"),
            (Ride.status.in_([
                RideStatus.DRIVER_EN_ROUTE,
                RideStatus.DRIVER_ARRIVED,
                RideStatus.IN_PROGRESS,
            ]), "In Transit"),
            (Ride.status == RideStatus.REQUESTED, "Pending"),
            (Ride.status.in_([
                RideStatus.CANCELLED,
                RideStatus.NO_SHOW,
            ]), "Cancelled"),
            else_="Other",
        ).label("display_status")

        result = await self.session.execute(
            select(display_status, func.count().label("count"))
            .where(*conditions)
            .group_by(display_status)
            .order_by(desc("count"))
        )
        return [{"status": row.display_status, "count": row.count} for row in result.all()]

    # ---- Top Performing Drivers ----

    async def get_top_drivers(
        self, days: int, limit: int = 5, business_id: UUID | None = None
    ) -> list[dict]:
        now = utc_now()
        since = now - timedelta(days=days)
        conditions = [
            Ride.deleted_at.is_(None),
            Ride.status == RideStatus.COMPLETED,
            Ride.driver_id.isnot(None),
            Ride.dropoff_at >= since,
        ]
        if business_id:
            conditions.append(Ride.assigned_to_business_id == business_id)

        # Subquery: trip counts per driver
        trip_sub = (
            select(
                Ride.driver_id,
                func.count().label("total_trips"),
            )
            .where(*conditions)
            .group_by(Ride.driver_id)
            .subquery()
        )

        # Subquery: average rating per driver (rider_to_driver ratings)
        rating_sub = (
            select(
                RideRating.rated_user_id.label("driver_id"),
                func.round(func.avg(RideRating.rating), 1).label("avg_rating"),
            )
            .where(RideRating.rating_type == "rider_to_driver")
            .group_by(RideRating.rated_user_id)
            .subquery()
        )

        result = await self.session.execute(
            select(
                trip_sub.c.driver_id,
                trip_sub.c.total_trips,
                func.coalesce(rating_sub.c.avg_rating, 0.0).label("avg_rating"),
            )
            .outerjoin(rating_sub, trip_sub.c.driver_id == rating_sub.c.driver_id)
            .order_by(desc(trip_sub.c.total_trips))
            .limit(limit)
        )
        return [
            {
                "driver_id": row.driver_id,
                "total_trips": row.total_trips,
                "average_rating": float(row.avg_rating),
            }
            for row in result.all()
        ]

    # ---- Recent Activity ----

    async def get_recent_activity(
        self, limit: int = 20, business_id: UUID | None = None
    ) -> list[dict]:
        conditions = [Ride.deleted_at.is_(None)]
        if business_id:
            conditions.append(Ride.assigned_to_business_id == business_id)

        # Get recent status transitions with ride info
        ride_ids_sub = (
            select(Ride.id)
            .where(*conditions)
            .subquery()
        )

        result = await self.session.execute(
            select(
                RideStatusLog.id,
                RideStatusLog.ride_id,
                RideStatusLog.from_status,
                RideStatusLog.to_status,
                RideStatusLog.timestamp,
                RideStatusLog.notes,
            )
            .where(RideStatusLog.ride_id.in_(select(ride_ids_sub)))
            .order_by(desc(RideStatusLog.timestamp))
            .limit(limit)
        )
        return [
            {
                "id": row.id,
                "ride_id": row.ride_id,
                "from_status": row.from_status,
                "to_status": row.to_status,
                "timestamp": row.timestamp,
                "notes": row.notes,
            }
            for row in result.all()
        ]
