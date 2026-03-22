import asyncio
import logging
from datetime import timedelta
from uuid import UUID

from app.clients.payment_service_client import PaymentServiceClient
from app.clients.user_service_client import UserServiceClient
from app.repositories.analytics_repo import AnalyticsRepository
from app.schemas.analytics import (
    ActivityEntry,
    DashboardKPIs,
    KPIChange,
    RecentActivityResponse,
    StatusSlice,
    TopDriverEntry,
    TopDriversResponse,
    TripStatusDistributionResponse,
    TripVolumePoint,
    TripVolumeTrendResponse,
)
from mediride_common.utils import utc_now

logger = logging.getLogger(__name__)

# Status transition -> human-readable activity
_EVENT_MAP = {
    "REQUESTED": ("booking_created", "New booking request received"),
    "PENDING_BUSINESS_ASSIGNMENT": ("business_assigned", "Ride assigned to fleet"),
    "CONFIRMED": ("ride_confirmed", "Ride confirmed"),
    "DRIVER_ASSIGNED": ("driver_assigned", "Driver assigned to trip"),
    "DRIVER_EN_ROUTE": ("driver_en_route", "Driver en route to pickup"),
    "DRIVER_ARRIVED": ("driver_arrived", "Driver arrived at pickup"),
    "IN_PROGRESS": ("trip_started", "Trip started"),
    "COMPLETED": ("trip_completed", "Trip completed"),
    "CANCELLED": ("trip_cancelled", "Trip cancelled"),
    "NO_SHOW": ("no_show", "Rider no-show recorded"),
}


class AnalyticsService:
    def __init__(
        self,
        analytics_repo: AnalyticsRepository,
        user_client: UserServiceClient,
        payment_client: PaymentServiceClient,
    ):
        self.repo = analytics_repo
        self.user_client = user_client
        self.payment_client = payment_client

    async def get_dashboard_kpis(
        self, business_id: UUID | None = None
    ) -> DashboardKPIs:
        now = utc_now()
        current_period_start = now - timedelta(days=30)
        previous_period_start = now - timedelta(days=60)

        # Run DB queries sequentially (async session cannot handle concurrent queries)
        total_trips = await self.repo.get_trip_count(business_id=business_id)
        active_drivers = await self.repo.get_active_driver_count(
            since=current_period_start, business_id=business_id
        )
        pending_bookings = await self.repo.get_pending_booking_count(business_id=business_id)
        revenue = await self.repo.get_revenue(business_id=business_id)

        # Previous period stats for comparison
        prev_trips = await self.repo.get_trip_count(
            since=previous_period_start, business_id=business_id
        )
        prev_drivers = await self.repo.get_active_driver_count(
            since=previous_period_start, business_id=business_id
        )
        prev_revenue = await self.repo.get_revenue(
            since=previous_period_start, business_id=business_id
        )

        # Current period only
        curr_trips = await self.repo.get_trip_count(
            since=current_period_start, business_id=business_id
        )
        curr_revenue = await self.repo.get_revenue(
            since=current_period_start, business_id=business_id
        )

        # Previous period only (subtract current from previous-60-day range)
        prev_only_trips = prev_trips - curr_trips
        prev_only_revenue = prev_revenue - curr_revenue

        return DashboardKPIs(
            total_trips=_build_kpi(total_trips, curr_trips, prev_only_trips),
            active_drivers=_build_kpi(active_drivers, active_drivers, prev_drivers),
            pending_bookings=_build_kpi(pending_bookings, 0, 0),
            revenue=_build_kpi(
                round(revenue, 2),
                round(curr_revenue, 2),
                round(prev_only_revenue, 2),
            ),
        )

    async def get_trip_volume_trend(
        self, days: int = 30, business_id: UUID | None = None
    ) -> TripVolumeTrendResponse:
        rows = await self.repo.get_trip_volume_trend(days=days, business_id=business_id)
        data = [TripVolumePoint(date=r["date"], count=r["count"]) for r in rows]
        total = sum(p.count for p in data)
        return TripVolumeTrendResponse(period_days=days, data=data, total=total)

    async def get_trip_status_distribution(
        self, business_id: UUID | None = None
    ) -> TripStatusDistributionResponse:
        rows = await self.repo.get_status_distribution(business_id=business_id)
        total = sum(r["count"] for r in rows)
        distribution = [
            StatusSlice(
                status=r["status"],
                count=r["count"],
                percentage=round((r["count"] / total * 100) if total else 0, 1),
            )
            for r in rows
        ]
        return TripStatusDistributionResponse(total=total, distribution=distribution)

    async def get_top_drivers(
        self, days: int = 30, limit: int = 5, business_id: UUID | None = None
    ) -> TopDriversResponse:
        rows = await self.repo.get_top_drivers(
            days=days, limit=limit, business_id=business_id
        )

        # Enrich with driver names from user-service (HTTP calls can run concurrently)
        async def _enrich(rank: int, row: dict) -> TopDriverEntry:
            profile = await self.user_client.get_driver_profile(row["driver_id"])
            name = "Unknown Driver"
            avatar_url = None
            if profile:
                name = (
                    f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip()
                    or "Unknown Driver"
                )
                avatar_url = profile.get("avatar_url")
            return TopDriverEntry(
                rank=rank,
                driver_id=row["driver_id"],
                driver_name=name,
                avatar_url=avatar_url,
                total_trips=row["total_trips"],
                average_rating=row["average_rating"],
            )

        drivers = await asyncio.gather(
            *[_enrich(i + 1, row) for i, row in enumerate(rows)]
        )
        return TopDriversResponse(period_days=days, drivers=list(drivers))

    async def get_recent_activity(
        self, limit: int = 20, business_id: UUID | None = None
    ) -> RecentActivityResponse:
        rows = await self.repo.get_recent_activity(limit=limit, business_id=business_id)
        activities = []
        for row in rows:
            to_status = row["to_status"]
            event_type, title = _EVENT_MAP.get(
                to_status, ("status_change", f"Status changed to {to_status}")
            )
            description = title
            if row["notes"]:
                description = f"{title} — {row['notes']}"

            activities.append(ActivityEntry(
                id=row["id"],
                event_type=event_type,
                title=title,
                description=description,
                ride_id=row["ride_id"],
                timestamp=row["timestamp"],
            ))
        return RecentActivityResponse(activities=activities)


def _build_kpi(total_value: float, current: float, previous: float) -> KPIChange:
    if previous > 0:
        change = round(((current - previous) / previous) * 100, 1)
    elif current > 0:
        change = 100.0
    else:
        change = 0.0

    if change > 0:
        trend = "up"
    elif change < 0:
        trend = "down"
    else:
        trend = "flat"

    return KPIChange(value=total_value, change_percent=change, trend=trend)
