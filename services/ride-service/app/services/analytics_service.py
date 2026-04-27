import asyncio
import logging
import re
from datetime import timedelta
from uuid import UUID

from app.clients.payment_service_client import PaymentServiceClient
from app.clients.user_service_client import UserServiceClient
from app.repositories.analytics_repo import AnalyticsRepository
from app.schemas.analytics import (
    ActivityEntry,
    BookingChannelEntry,
    BookingChannelsResponse,
    BookingSourceSplit,
    DashboardKPIs,
    FleetPartnerEntry,
    KPIChange,
    RecentActivityResponse,
    ServiceQualityResponse,
    StatusSlice,
    TopDriverEntry,
    TopDriversResponse,
    TopFacilitiesResponse,
    TopFacilityEntry,
    TopFleetPartnersResponse,
    TransportDistributionResponse,
    TransportTypeSlice,
    TripStatusDistributionResponse,
    TripVolumePoint,
    TripVolumeTrendResponse,
)
from mediride_common.schemas.enums import RideStatus
from mediride_common.utils import utc_now

logger = logging.getLogger(__name__)

# Status transition -> human-readable activity
_EVENT_MAP = {
    RideStatus.REQUESTED: ("booking_created", "New booking request received"),
    RideStatus.PENDING_BUSINESS_ASSIGNMENT: ("business_assigned", "Ride assigned to fleet"),
    RideStatus.CONFIRMED: ("ride_confirmed", "Ride confirmed"),
    RideStatus.DRIVER_ASSIGNED: ("driver_assigned", "Driver assigned to trip"),
    RideStatus.DRIVER_EN_ROUTE: ("driver_en_route", "Driver en route to pickup"),
    RideStatus.DRIVER_ARRIVED: ("driver_arrived", "Driver arrived at pickup"),
    RideStatus.IN_PROGRESS: ("trip_started", "Trip started"),
    RideStatus.COMPLETED: ("trip_completed", "Trip completed"),
    RideStatus.CANCELLED: ("trip_cancelled", "Trip cancelled"),
    RideStatus.NO_SHOW: ("no_show", "Rider no-show recorded"),
}
_UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


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
        total_bookings = await self.repo.get_trip_count(business_id=business_id)
        active_clients = await self.repo.get_unique_client_count(
            since=current_period_start, business_id=business_id
        )
        revenue = await self.repo.get_revenue(business_id=business_id)

        # Facility count via user-service (HTTP call)
        facility_count = await self.user_client.get_facility_count()

        # Previous period stats for comparison
        prev_bookings = await self.repo.get_trip_count(
            since=previous_period_start, business_id=business_id
        )
        prev_clients = await self.repo.get_unique_client_count(
            since=previous_period_start, business_id=business_id
        )
        prev_revenue = await self.repo.get_revenue(
            since=previous_period_start, business_id=business_id
        )

        # Current period only
        curr_bookings = await self.repo.get_trip_count(
            since=current_period_start, business_id=business_id
        )
        curr_revenue = await self.repo.get_revenue(
            since=current_period_start, business_id=business_id
        )

        # Previous period only (subtract current from previous-60-day range)
        prev_only_bookings = prev_bookings - curr_bookings
        prev_only_clients = prev_clients - active_clients
        prev_only_revenue = prev_revenue - curr_revenue

        return DashboardKPIs(
            total_bookings=_build_kpi(total_bookings, curr_bookings, prev_only_bookings),
            active_clients=_build_kpi(active_clients, active_clients, prev_only_clients),
            registered_facilities=_build_kpi(facility_count, 0, 0),
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
        name_by_id = await self._get_activity_name_map(rows)
        activities = []
        for row in rows:
            to_status = row["to_status"]
            event_type, title = _EVENT_MAP.get(
                to_status,
                ("status_change", f"Status changed to {_format_status_label(to_status)}"),
            )
            description = title
            notes = _format_activity_notes(row["notes"], name_by_id)
            if notes:
                description = f"{title} - {notes}"

            activities.append(ActivityEntry(
                id=row["id"],
                event_type=event_type,
                title=title,
                description=description,
                ride_id=row["ride_id"],
                timestamp=row["timestamp"],
            ))
        return RecentActivityResponse(activities=activities)

    async def _get_activity_name_map(self, rows: list[dict]) -> dict[str, str]:
        ids: set[UUID] = set()
        for row in rows:
            for match in _UUID_PATTERN.findall(row.get("notes") or ""):
                ids.add(UUID(match))

        if not ids:
            return {}

        try:
            users = await self.user_client.batch_get_users(list(ids))
        except Exception as exc:
            logger.error(f"Failed to resolve activity names: {exc}")
            return {}

        name_by_id: dict[str, str] = {}
        for user in users:
            user_id = user.get("id")
            if not user_id:
                continue
            name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            if name:
                name_by_id[user_id] = name
        return name_by_id

    async def get_transport_distribution(
        self, days: int = 30, business_id: UUID | None = None
    ) -> TransportDistributionResponse:
        rows = await self.repo.get_transport_type_distribution(
            days=days, business_id=business_id
        )
        total = sum(r["count"] for r in rows)
        distribution = [
            TransportTypeSlice(
                transport_type=r["transport_type"],
                count=r["count"],
                percentage=round((r["count"] / total * 100) if total else 0, 1),
            )
            for r in rows
        ]

        source = await self.repo.get_booking_source_split(
            days=days, business_id=business_id
        )
        src_total = source["total"] or 1
        booking_source = BookingSourceSplit(
            client_bookings_percent=round(source["client"] / src_total * 100),
            facility_bookings_percent=round(source["facility"] / src_total * 100),
        )

        return TransportDistributionResponse(
            period_days=days,
            total=total,
            distribution=distribution,
            booking_source=booking_source,
        )

    async def get_top_fleet_partners(
        self, days: int = 30, limit: int = 6, business_id: UUID | None = None
    ) -> TopFleetPartnersResponse:
        rows = await self.repo.get_top_fleet_partners(
            days=days, limit=limit, business_id=business_id
        )
        if not rows:
            return TopFleetPartnersResponse(period_days=days, partners=[])

        fleet_ids = [row["fleet_id"] for row in rows]
        fleet_data = await self.user_client.get_fleets_with_vehicle_counts(fleet_ids)

        partners = []
        for i, row in enumerate(rows):
            fid = str(row["fleet_id"])
            info = fleet_data.get(fid, {})
            partners.append(
                FleetPartnerEntry(
                    rank=i + 1,
                    fleet_id=row["fleet_id"],
                    fleet_name=info.get("name", "Unknown Fleet"),
                    logo_url=info.get("logo_url"),
                    vehicle_count=info.get("vehicle_count", 0),
                    total_trips=row["total_trips"],
                    average_rating=row["average_rating"],
                )
            )
        return TopFleetPartnersResponse(period_days=days, partners=partners)

    async def get_booking_channels(
        self, days: int = 30, business_id: UUID | None = None
    ) -> BookingChannelsResponse:
        rows = await self.repo.get_booking_channel_breakdown(
            days=days, business_id=business_id
        )
        total = sum(r["count"] for r in rows)
        channels = [
            BookingChannelEntry(
                channel=r["channel"],
                count=r["count"],
                percentage=round((r["count"] / total * 100) if total else 0, 1),
                growth_percent=r["growth_percent"],
            )
            for r in rows
        ]
        return BookingChannelsResponse(
            period_days=days, total=total, channels=channels
        )

    async def get_service_quality(
        self, business_id: UUID | None = None
    ) -> ServiceQualityResponse:
        avg_pickup = await self.repo.get_avg_pickup_time_minutes(
            business_id=business_id
        )
        avg_distance = await self.repo.get_avg_trip_distance_km(
            business_id=business_id
        )
        rating = await self.repo.get_service_rating_avg(business_id=business_id)
        completion = await self.repo.get_completion_rate(business_id=business_id)

        return ServiceQualityResponse(
            avg_pickup_time_minutes=avg_pickup,
            avg_trip_distance_km=avg_distance,
            service_rating=rating,
            completion_rate_percent=completion,
        )

    async def get_top_facilities(
        self, days: int = 30, limit: int = 5, business_id: UUID | None = None
    ) -> TopFacilitiesResponse:
        rows = await self.repo.get_facility_booking_stats(
            days=days, limit=limit, business_id=business_id
        )
        if not rows:
            return TopFacilitiesResponse(
                period_days=days,
                total_facilities=0,
                type_counts={},
                facilities=[],
            )

        facility_ids = [row["facility_id"] for row in rows]
        facility_data = await self.user_client.get_top_facilities(facility_ids)

        facilities = []
        type_counts: dict[str, int] = {}
        for i, row in enumerate(rows):
            fid = str(row["facility_id"])
            info = facility_data.get(fid, {})
            f_type = info.get("facility_type", "Unknown")
            type_counts[f_type] = type_counts.get(f_type, 0) + 1
            facilities.append(
                TopFacilityEntry(
                    rank=i + 1,
                    facility_id=row["facility_id"],
                    facility_name=info.get("name", "Unknown Facility"),
                    facility_type=f_type,
                    total_bookings=row["total_bookings"],
                    acceptance_rate=row["acceptance_rate"],
                )
            )

        total_facilities = await self.user_client.get_facility_count()
        return TopFacilitiesResponse(
            period_days=days,
            total_facilities=total_facilities,
            type_counts=type_counts,
            facilities=facilities,
        )


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


def _format_status_label(status: str | None) -> str:
    if not status:
        return "Status Updated"
    return status.replace("_", " ").strip().title()


def _format_activity_notes(notes: str | None, name_by_id: dict[str, str]) -> str | None:
    if not notes:
        return None

    formatted = notes
    for match in _UUID_PATTERN.findall(notes):
        replacement = name_by_id.get(match)
        if replacement:
            formatted = formatted.replace(match, replacement)

    if formatted.startswith("Admin assigned driver "):
        return f"Assigned to {formatted.removeprefix('Admin assigned driver ')}"
    if formatted.startswith("Admin assigned caregiver "):
        return f"Caregiver assigned: {formatted.removeprefix('Admin assigned caregiver ')}"
    if formatted.startswith("Driver reassigned: "):
        return formatted.replace(" → ", " to ")

    return formatted
