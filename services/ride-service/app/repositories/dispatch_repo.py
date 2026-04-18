"""Repository for dispatch center operations."""
import uuid
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dispatch_settings import DispatchSettings
from app.models.ride import Ride


class DispatchRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_dispatch_kpis(self) -> dict:
        """Get KPIs for dispatch center dashboard."""
        # Pending assignments (confirmed but no driver assigned)
        pending_result = await self.session.execute(
            select(func.count())
            .select_from(Ride)
            .where(
                Ride.status == "confirmed",
                Ride.driver_id.is_(None),
                Ride.deleted_at.is_(None),
            )
        )
        pending_assignments = pending_result.scalar_one()

        # Assigned today (driver assigned in last 24 hours)
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        assigned_today_result = await self.session.execute(
            select(func.count())
            .select_from(Ride)
            .where(
                Ride.status.in_(["driver_assigned", "driver_en_route", "driver_arrived", "in_progress"]),
                Ride.created_at >= today_start,
                Ride.deleted_at.is_(None),
            )
        )
        assigned_today = assigned_today_result.scalar_one()

        # Drivers on trip (active ride statuses)
        on_trip_result = await self.session.execute(
            select(func.count(func.distinct(Ride.driver_id)))
            .where(
                Ride.status.in_(["driver_en_route", "driver_arrived", "in_progress"]),
                Ride.driver_id.isnot(None),
                Ride.deleted_at.is_(None),
            )
        )
        drivers_on_trip = on_trip_result.scalar_one()

        return {
            "pending_assignments": pending_assignments,
            "assigned_today": assigned_today,
            "available_drivers": 0,  # Will be enriched by service layer via user-service
            "drivers_on_trip": drivers_on_trip,
        }

    async def get_unassigned_rides(
        self, limit: int = 50, offset: int = 0
    ) -> tuple[list[Ride], int]:
        """Get rides that need driver assignment."""
        query = (
            select(Ride)
            .where(
                Ride.status == "confirmed",
                Ride.driver_id.is_(None),
                Ride.deleted_at.is_(None),
            )
            .order_by(Ride.scheduled_at.asc())
        )

        # Count
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        # Paginated results
        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        rides = list(result.scalars().all())

        return rides, total

    async def get_rides_by_ids(self, ride_ids: list[UUID]) -> list[Ride]:
        """Fetch multiple rides by their IDs."""
        result = await self.session.execute(
            select(Ride).where(Ride.id.in_(ride_ids))
        )
        return list(result.scalars().all())

    # --- Dispatch Settings CRUD ---

    async def get_dispatch_settings(self) -> DispatchSettings | None:
        """Get the current dispatch settings (singleton)."""
        result = await self.session.execute(
            select(DispatchSettings).order_by(DispatchSettings.updated_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def create_dispatch_settings(self, **kwargs) -> DispatchSettings:
        """Create initial dispatch settings."""
        settings = DispatchSettings(id=uuid.uuid4(), **kwargs)
        self.session.add(settings)
        await self.session.flush()
        await self.session.refresh(settings)
        return settings

    async def update_dispatch_settings(
        self, settings_id: UUID, **kwargs
    ) -> DispatchSettings | None:
        """Update existing dispatch settings."""
        result = await self.session.execute(
            select(DispatchSettings).where(DispatchSettings.id == settings_id)
        )
        settings = result.scalar_one_or_none()
        if not settings:
            return None

        for key, value in kwargs.items():
            setattr(settings, key, value)

        await self.session.flush()
        await self.session.refresh(settings)
        return settings

    async def get_rides_for_auto_dispatch(
        self, scheduled_window_hours: int = 24
    ) -> list[Ride]:
        """
        Get rides eligible for auto-dispatch.
        Criteria: confirmed, no driver, scheduled within next N hours.
        """
        now = datetime.utcnow()
        window_end = now + timedelta(hours=scheduled_window_hours)

        result = await self.session.execute(
            select(Ride)
            .where(
                and_(
                    Ride.status == "confirmed",
                    Ride.driver_id.is_(None),
                    Ride.scheduled_at >= now,
                    Ride.scheduled_at <= window_end,
                    Ride.deleted_at.is_(None),
                )
            )
            .order_by(Ride.scheduled_at.asc())
        )
        return list(result.scalars().all())

    async def assign_driver_to_ride(
        self, ride_id: UUID, driver_id: UUID, business_id: UUID | None = None
    ) -> Ride | None:
        """Assign a driver to a ride and update status."""
        result = await self.session.execute(
            select(Ride).where(Ride.id == ride_id)
        )
        ride = result.scalar_one_or_none()
        if not ride:
            return None

        ride.driver_id = driver_id
        ride.business_id = business_id
        ride.status = "driver_assigned"

        await self.session.flush()
        await self.session.refresh(ride)
        return ride

    async def get_active_trips(self) -> list[Ride]:
        """
        Get all active trips for live dispatch map view.
        Includes trips with driver assigned, en route, arrived, or in progress.
        """
        result = await self.session.execute(
            select(Ride)
            .where(
                Ride.status.in_(["driver_assigned", "driver_en_route", "driver_arrived", "in_progress"]),
                Ride.deleted_at.is_(None),
            )
            .order_by(Ride.scheduled_at.desc())
        )
        return list(result.scalars().all())
