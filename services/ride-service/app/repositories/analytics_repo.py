from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import Date, String, case, cast, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ride import Ride
from app.models.ride_rating import RideRating
from app.models.ride_status_log import RideStatusLog
from mediride_common.schemas.enums import RideStatus, RideType
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

    # ---- Transport Type Distribution ----

    async def get_transport_type_distribution(
        self, days: int = 30, business_id: UUID | None = None
    ) -> list[dict]:
        now = utc_now()
        since = now - timedelta(days=days)
        conditions = [
            Ride.deleted_at.is_(None),
            Ride.created_at >= since,
        ]
        if business_id:
            conditions.append(Ride.assigned_to_business_id == business_id)

        display_type = case(
            (Ride.ride_type == RideType.WHEELCHAIR, "Wheelchair Accessible"),
            (Ride.ride_type == RideType.STRETCHER, "Stretcher Transport"),
            else_="Ambulatory",
        ).label("transport_type")

        result = await self.session.execute(
            select(display_type, func.count().label("count"))
            .where(*conditions)
            .group_by(display_type)
            .order_by(desc("count"))
        )
        return [
            {"transport_type": row.transport_type, "count": row.count}
            for row in result.all()
        ]

    async def get_booking_source_split(
        self, days: int = 30, business_id: UUID | None = None
    ) -> dict:
        now = utc_now()
        since = now - timedelta(days=days)
        conditions = [
            Ride.deleted_at.is_(None),
            Ride.created_at >= since,
        ]
        if business_id:
            conditions.append(Ride.assigned_to_business_id == business_id)

        result = await self.session.execute(
            select(
                func.count().label("total"),
                func.count().filter(
                    Ride.facility_id.isnot(None),
                ).label("facility_count"),
            ).where(*conditions)
        )
        row = result.one()
        total = row.total or 0
        facility = row.facility_count or 0
        client = total - facility
        return {
            "total": total,
            "client": client,
            "facility": facility,
        }

    # ---- Unique Client Count ----

    async def get_unique_client_count(
        self, since: datetime | None = None, business_id: UUID | None = None
    ) -> int:
        conditions = [Ride.deleted_at.is_(None)]
        if since:
            conditions.append(Ride.created_at >= since)
        if business_id:
            conditions.append(Ride.assigned_to_business_id == business_id)
        result = await self.session.execute(
            select(func.count(func.distinct(Ride.rider_id))).where(*conditions)
        )
        return result.scalar_one()

    # ---- Booking Channel Breakdown ----

    async def get_booking_channel_breakdown(
        self, days: int = 30, business_id: UUID | None = None
    ) -> list[dict]:
        now = utc_now()
        since = now - timedelta(days=days)
        prev_since = now - timedelta(days=days * 2)
        conditions = [
            Ride.deleted_at.is_(None),
            Ride.created_at >= since,
        ]
        if business_id:
            conditions.append(Ride.assigned_to_business_id == business_id)

        channel_label = case(
            (Ride.booking_channel == "mobile_app", "Mobile App"),
            (Ride.booking_channel == "website_client", "Website (Client)"),
            (Ride.booking_channel == "website_facility", "Website (Facility)"),
            else_="Other",
        ).label("channel")

        result = await self.session.execute(
            select(channel_label, func.count().label("count"))
            .where(*conditions)
            .group_by(channel_label)
            .order_by(desc("count"))
        )
        current = [{"channel": r.channel, "count": r.count} for r in result.all()]

        # Previous period for growth calc
        prev_conditions = [
            Ride.deleted_at.is_(None),
            Ride.created_at >= prev_since,
            Ride.created_at < since,
        ]
        if business_id:
            prev_conditions.append(Ride.assigned_to_business_id == business_id)

        prev_result = await self.session.execute(
            select(channel_label, func.count().label("count"))
            .where(*prev_conditions)
            .group_by(channel_label)
        )
        prev_map = {r.channel: r.count for r in prev_result.all()}

        for item in current:
            prev_count = prev_map.get(item["channel"], 0)
            if prev_count > 0:
                item["growth_percent"] = round(
                    ((item["count"] - prev_count) / prev_count) * 100, 1
                )
            elif item["count"] > 0:
                item["growth_percent"] = 100.0
            else:
                item["growth_percent"] = 0.0

        return current

    # ---- Service Quality Metrics ----

    async def get_avg_pickup_time_minutes(
        self, business_id: UUID | None = None
    ) -> float:
        """Average minutes from DRIVER_ASSIGNED to DRIVER_ARRIVED."""
        assigned_sub = (
            select(
                RideStatusLog.ride_id,
                func.min(RideStatusLog.timestamp).label("assigned_at"),
            )
            .where(RideStatusLog.to_status == RideStatus.DRIVER_ASSIGNED)
            .group_by(RideStatusLog.ride_id)
            .subquery()
        )
        arrived_sub = (
            select(
                RideStatusLog.ride_id,
                func.min(RideStatusLog.timestamp).label("arrived_at"),
            )
            .where(RideStatusLog.to_status == RideStatus.DRIVER_ARRIVED)
            .group_by(RideStatusLog.ride_id)
            .subquery()
        )
        conditions = []
        if business_id:
            conditions.append(Ride.assigned_to_business_id == business_id)
            conditions.append(Ride.deleted_at.is_(None))

        q = (
            select(
                func.avg(
                    func.extract(
                        "epoch",
                        arrived_sub.c.arrived_at - assigned_sub.c.assigned_at,
                    )
                    / 60
                ).label("avg_minutes")
            )
            .select_from(assigned_sub)
            .join(arrived_sub, assigned_sub.c.ride_id == arrived_sub.c.ride_id)
        )
        if conditions:
            q = q.join(Ride, assigned_sub.c.ride_id == Ride.id).where(*conditions)

        result = await self.session.execute(q)
        val = result.scalar_one_or_none()
        return round(float(val), 1) if val else 0.0

    async def get_avg_trip_distance_km(
        self, business_id: UUID | None = None
    ) -> float:
        conditions = [
            Ride.deleted_at.is_(None),
            Ride.status == RideStatus.COMPLETED,
            Ride.actual_distance_miles.isnot(None),
        ]
        if business_id:
            conditions.append(Ride.assigned_to_business_id == business_id)
        result = await self.session.execute(
            select(func.avg(Ride.actual_distance_miles * 1.60934)).where(*conditions)
        )
        val = result.scalar_one_or_none()
        return round(float(val), 1) if val else 0.0

    async def get_service_rating_avg(
        self, business_id: UUID | None = None
    ) -> float:
        conditions = [RideRating.rating_type == "rider_to_driver"]
        if business_id:
            q = (
                select(func.round(func.avg(RideRating.rating), 1))
                .join(Ride, RideRating.ride_id == Ride.id)
                .where(
                    *conditions,
                    Ride.assigned_to_business_id == business_id,
                    Ride.deleted_at.is_(None),
                )
            )
        else:
            q = select(func.round(func.avg(RideRating.rating), 1)).where(*conditions)
        result = await self.session.execute(q)
        val = result.scalar_one_or_none()
        return float(val) if val else 0.0

    async def get_completion_rate(
        self, business_id: UUID | None = None
    ) -> float:
        conditions = [Ride.deleted_at.is_(None)]
        if business_id:
            conditions.append(Ride.assigned_to_business_id == business_id)
        total_result = await self.session.execute(
            select(func.count()).where(*conditions)
        )
        total = total_result.scalar_one()
        if total == 0:
            return 0.0
        completed_result = await self.session.execute(
            select(func.count()).where(
                *conditions, Ride.status == RideStatus.COMPLETED
            )
        )
        completed = completed_result.scalar_one()
        return round((completed / total) * 100, 1)

    # ---- Top Facilities ----

    async def get_facility_booking_stats(
        self, days: int = 30, limit: int = 5, business_id: UUID | None = None
    ) -> list[dict]:
        now = utc_now()
        since = now - timedelta(days=days)
        conditions = [
            Ride.deleted_at.is_(None),
            Ride.facility_id.isnot(None),
            Ride.created_at >= since,
        ]
        if business_id:
            conditions.append(Ride.assigned_to_business_id == business_id)

        total_sub = (
            select(
                Ride.facility_id,
                func.count().label("total_bookings"),
            )
            .where(*conditions)
            .group_by(Ride.facility_id)
            .subquery()
        )

        completed_conditions = conditions + [Ride.status == RideStatus.COMPLETED]
        completed_sub = (
            select(
                Ride.facility_id,
                func.count().label("completed"),
            )
            .where(*completed_conditions)
            .group_by(Ride.facility_id)
            .subquery()
        )

        result = await self.session.execute(
            select(
                total_sub.c.facility_id,
                total_sub.c.total_bookings,
                func.coalesce(completed_sub.c.completed, 0).label("completed"),
            )
            .outerjoin(
                completed_sub,
                total_sub.c.facility_id == completed_sub.c.facility_id,
            )
            .order_by(desc(total_sub.c.total_bookings))
            .limit(limit)
        )
        return [
            {
                "facility_id": row.facility_id,
                "total_bookings": row.total_bookings,
                "acceptance_rate": round(
                    (row.completed / row.total_bookings * 100)
                    if row.total_bookings > 0
                    else 0,
                    1,
                ),
            }
            for row in result.all()
        ]

    # ---- Top Fleet Partners ----

    async def get_top_fleet_partners(
        self, days: int = 30, limit: int = 6, business_id: UUID | None = None
    ) -> list[dict]:
        now = utc_now()
        since = now - timedelta(days=days)
        conditions = [
            Ride.deleted_at.is_(None),
            Ride.status == RideStatus.COMPLETED,
            Ride.assigned_to_business_id.isnot(None),
            Ride.dropoff_at >= since,
        ]
        if business_id:
            conditions.append(Ride.assigned_to_business_id == business_id)

        # Subquery: trip counts per fleet
        trip_sub = (
            select(
                Ride.assigned_to_business_id.label("fleet_id"),
                func.count().label("total_trips"),
            )
            .where(*conditions)
            .group_by(Ride.assigned_to_business_id)
            .subquery()
        )

        # Subquery: average rating per fleet (driver ratings for drivers in that fleet)
        rating_conditions = [
            Ride.deleted_at.is_(None),
            Ride.assigned_to_business_id.isnot(None),
            Ride.dropoff_at >= since,
            RideRating.rating_type == "rider_to_driver",
        ]
        rating_sub = (
            select(
                Ride.assigned_to_business_id.label("fleet_id"),
                func.round(func.avg(RideRating.rating), 1).label("avg_rating"),
            )
            .join(Ride, RideRating.ride_id == Ride.id)
            .where(*rating_conditions)
            .group_by(Ride.assigned_to_business_id)
            .subquery()
        )

        result = await self.session.execute(
            select(
                trip_sub.c.fleet_id,
                trip_sub.c.total_trips,
                func.coalesce(rating_sub.c.avg_rating, 0.0).label("avg_rating"),
            )
            .outerjoin(rating_sub, trip_sub.c.fleet_id == rating_sub.c.fleet_id)
            .order_by(desc(trip_sub.c.total_trips))
            .limit(limit)
        )
        return [
            {
                "fleet_id": row.fleet_id,
                "total_trips": row.total_trips,
                "average_rating": float(row.avg_rating),
            }
            for row in result.all()
        ]
