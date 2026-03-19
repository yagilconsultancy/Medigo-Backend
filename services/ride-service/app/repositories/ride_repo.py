from datetime import datetime
from uuid import UUID

from sqlalchemy import Numeric, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ride import Ride
from mediride_common.schemas.enums import RideStatus
from mediride_common.utils import utc_now


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
                RideStatus.REQUESTED, RideStatus.PENDING_BUSINESS_ASSIGNMENT,
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

    # ---- Admin & Business Assignment Queries ----

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

    async def get_pending_for_business(
        self, business_id: UUID, offset: int = 0, limit: int = 20
    ) -> tuple[list[Ride], int]:
        base_query = select(Ride).where(
            Ride.assigned_to_business_id == business_id,
            Ride.status == RideStatus.PENDING_BUSINESS_ASSIGNMENT,
            Ride.deleted_at.is_(None),
        )
        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            base_query.offset(offset).limit(limit)
            .order_by(Ride.assigned_to_business_at.asc())
        )
        return list(result.scalars().all()), total

    async def get_by_business(
        self,
        business_id: UUID,
        status_filter: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Ride], int]:
        conditions = [
            Ride.assigned_to_business_id == business_id,
            Ride.deleted_at.is_(None),
        ]
        if status_filter:
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

    async def get_expired_business_assignments(self) -> list[Ride]:
        now = utc_now()
        result = await self.session.execute(
            select(Ride).where(
                Ride.status == RideStatus.PENDING_BUSINESS_ASSIGNMENT,
                Ride.business_assignment_expires_at.isnot(None),
                Ride.business_assignment_expires_at <= now,
                Ride.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())
