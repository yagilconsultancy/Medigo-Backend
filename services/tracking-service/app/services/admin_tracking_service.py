import asyncio
import logging
from uuid import UUID

from app.clients.ride_service_client import RideServiceClient
from app.clients.user_service_client import UserServiceClient
from app.repositories.location_history_repo import LocationHistoryRepository
from app.repositories.tracking_session_repo import TrackingSessionRepository
from app.schemas.admin_tracking import (
    ActiveTripDetail,
    ActiveTripKPIs,
    ActiveTripOverview,
    LiveDriverEntry,
    LocationPoint,
)
from mediride_common.schemas.enums import TrackingSessionStatus
from mediride_common.utils import utc_now

logger = logging.getLogger(__name__)


class AdminTrackingService:
    def __init__(
        self,
        session_repo: TrackingSessionRepository,
        history_repo: LocationHistoryRepository,
        ride_client: RideServiceClient,
        user_client: UserServiceClient,
    ):
        self.session_repo = session_repo
        self.history_repo = history_repo
        self.ride_client = ride_client
        self.user_client = user_client

    # ---- KPIs ----

    async def get_active_trip_kpis(self) -> ActiveTripKPIs:
        # DB queries must be sequential (same async session)
        active_count = await self.session_repo.get_active_count()
        arriving_soon = await self.session_repo.get_arriving_soon_count()
        avg_speed = await self.session_repo.get_avg_speed()
        # HTTP call can run after DB queries
        completed_today = await self.ride_client.get_completed_today_count()
        return ActiveTripKPIs(
            active_trips=active_count,
            arriving_soon=arriving_soon,
            avg_speed=round(avg_speed, 1) if avg_speed is not None else None,
            completed_today=completed_today,
        )

    # ---- Active Trips List ----

    async def get_active_trips(self) -> list[ActiveTripOverview]:
        sessions = await self.session_repo.get_all_active_sessions()
        if not sessions:
            return []

        # Batch fetch ride data
        ride_ids = [s.ride_id for s in sessions]
        driver_ids = list({s.driver_id for s in sessions})
        rider_ids = list({s.rider_id for s in sessions})

        rides_task = self.ride_client.get_active_rides()
        driver_tasks = [self.user_client.get_driver_profile(did) for did in driver_ids]
        rider_tasks = [self.user_client.get_user_profile(rid) for rid in rider_ids]

        results = await asyncio.gather(
            rides_task, *driver_tasks, *rider_tasks,
            return_exceptions=True,
        )

        # Parse results
        rides_list = results[0] if not isinstance(results[0], Exception) else []
        ride_map = {r["id"]: r for r in rides_list} if isinstance(rides_list, list) else {}

        driver_profiles = {}
        for i, did in enumerate(driver_ids):
            res = results[1 + i]
            if not isinstance(res, Exception) and res:
                driver_profiles[str(did)] = res

        rider_profiles = {}
        offset = 1 + len(driver_ids)
        for i, rid in enumerate(rider_ids):
            res = results[offset + i]
            if not isinstance(res, Exception) and res:
                rider_profiles[str(rid)] = res

        trips = []
        for s in sessions:
            ride_data = ride_map.get(str(s.ride_id), {})
            driver = driver_profiles.get(str(s.driver_id), {})
            rider = rider_profiles.get(str(s.rider_id), {})

            trips.append(self._build_overview(s, ride_data, driver, rider))

        return trips

    # ---- Trip Detail ----

    async def get_trip_detail(self, ride_id: UUID) -> ActiveTripDetail | None:
        session = await self.session_repo.get_active_by_ride_id(ride_id)
        if not session:
            return None

        # DB query must run separately from HTTP calls
        history = await self.history_repo.get_recent_by_session(session.id, limit=100)

        # HTTP calls can run in parallel
        ride_data, driver, rider = await asyncio.gather(
            self.ride_client.get_ride(ride_id),
            self.user_client.get_driver_profile(session.driver_id),
            self.user_client.get_user_profile(session.rider_id),
        )

        ride_data = ride_data or {}
        driver = driver or {}
        rider = rider or {}

        overview = self._build_overview(session, ride_data, driver, rider)
        route_points = [
            LocationPoint(
                latitude=float(h.latitude),
                longitude=float(h.longitude),
                heading=float(h.heading) if h.heading else None,
                speed=float(h.speed) if h.speed else None,
                recorded_at=h.recorded_at,
            )
            for h in history
        ]

        return ActiveTripDetail(
            **overview.model_dump(),
            special_instructions=ride_data.get("special_instructions"),
            mobility_level=ride_data.get("mobility_level"),
            estimated_distance=ride_data.get("estimated_distance_km"),
            estimated_duration=ride_data.get("estimated_duration_minutes"),
            driver_rating=driver.get("rating"),
            driver_phone=driver.get("phone"),
            route_history=route_points,
        )

    # ---- Live Drivers ----

    async def get_live_drivers(self) -> list[LiveDriverEntry]:
        sessions = await self.session_repo.get_all_active_sessions()
        if not sessions:
            return []

        driver_ids = list({s.driver_id for s in sessions})
        ride_ids = [s.ride_id for s in sessions]

        rides_task = self.ride_client.get_active_rides()
        driver_tasks = [self.user_client.get_driver_profile(did) for did in driver_ids]

        results = await asyncio.gather(
            rides_task, *driver_tasks,
            return_exceptions=True,
        )

        rides_list = results[0] if not isinstance(results[0], Exception) else []
        ride_map = {r["id"]: r for r in rides_list} if isinstance(rides_list, list) else {}

        driver_profiles = {}
        for i, did in enumerate(driver_ids):
            res = results[1 + i]
            if not isinstance(res, Exception) and res:
                driver_profiles[str(did)] = res

        entries = []
        for s in sessions:
            driver = driver_profiles.get(str(s.driver_id), {})
            ride_data = ride_map.get(str(s.ride_id), {})

            # Build driver name from first_name and last_name
            driver_name_parts = [
                driver.get("first_name", ""),
                driver.get("last_name", ""),
            ]
            driver_name = " ".join(p for p in driver_name_parts if p) or None

            # Build vehicle string
            vehicle_parts = [
                driver.get("vehicle_make", ""),
                driver.get("vehicle_model", ""),
            ]
            vehicle_str = " ".join(p for p in vehicle_parts if p) or None

            entries.append(LiveDriverEntry(
                driver_id=s.driver_id,
                driver_name=driver_name,
                driver_avatar=driver.get("avatar_url"),
                driver_vehicle=vehicle_str,
                current_latitude=float(s.current_latitude) if s.current_latitude else None,
                current_longitude=float(s.current_longitude) if s.current_longitude else None,
                current_heading=float(s.current_heading) if s.current_heading else None,
                current_speed=float(s.current_speed) if s.current_speed else None,
                ride_id=s.ride_id,
                trip_id_display=_generate_trip_display_id(s.ride_id),
                trip_status=_derive_trip_status(
                    float(s.eta_minutes) if s.eta_minutes else None,
                    s.status,
                ),
                eta_minutes=float(s.eta_minutes) if s.eta_minutes else None,
                pickup_address=ride_data.get("pickup_address"),
                destination_address=ride_data.get("destination_address"),
            ))

        return entries

    # ---- Helpers ----

    def _build_overview(
        self, session, ride_data: dict, driver: dict, rider: dict,
    ) -> ActiveTripOverview:
        # Build driver name from first_name and last_name
        driver_name_parts = [
            driver.get("first_name", ""),
            driver.get("last_name", ""),
        ]
        driver_name = " ".join(p for p in driver_name_parts if p) or None

        # Build vehicle string
        vehicle_parts = [
            driver.get("vehicle_make", ""),
            driver.get("vehicle_model", ""),
        ]
        vehicle_str = " ".join(p for p in vehicle_parts if p) or None

        # Build rider name from first_name and last_name
        rider_name_parts = [
            rider.get("first_name", ""),
            rider.get("last_name", ""),
        ]
        rider_name = " ".join(p for p in rider_name_parts if p) or None

        eta = float(session.eta_minutes) if session.eta_minutes else None
        distance_remaining = float(session.distance_remaining_miles) if session.distance_remaining_miles else None

        estimated_dist = ride_data.get("estimated_distance_km")
        progress = _calculate_progress(estimated_dist, distance_remaining)
        elapsed = _calculate_elapsed_minutes(session.started_at)

        return ActiveTripOverview(
            session_id=session.id,
            ride_id=session.ride_id,
            trip_id_display=_generate_trip_display_id(session.ride_id),
            status=_derive_trip_status(eta, session.status),
            driver_id=session.driver_id,
            driver_name=driver_name,
            driver_avatar=driver.get("avatar_url"),
            driver_vehicle=vehicle_str,
            rider_id=session.rider_id,
            patient_name=rider_name,
            current_latitude=float(session.current_latitude) if session.current_latitude else None,
            current_longitude=float(session.current_longitude) if session.current_longitude else None,
            current_heading=float(session.current_heading) if session.current_heading else None,
            current_speed=float(session.current_speed) if session.current_speed else None,
            eta_minutes=eta,
            distance_remaining=distance_remaining,
            progress_percent=progress,
            pickup_address=ride_data.get("pickup_address"),
            pickup_latitude=float(session.pickup_latitude) if session.pickup_latitude else None,
            pickup_longitude=float(session.pickup_longitude) if session.pickup_longitude else None,
            destination_address=ride_data.get("destination_address"),
            destination_latitude=float(session.destination_latitude) if session.destination_latitude else None,
            destination_longitude=float(session.destination_longitude) if session.destination_longitude else None,
            ride_type=ride_data.get("ride_type"),
            medical_alerts=_extract_medical_alerts(ride_data),
            started_at=session.started_at,
            elapsed_minutes=elapsed,
        )


def _generate_trip_display_id(ride_id: UUID) -> str:
    return f"TR-{str(ride_id).replace('-', '')[-4:].upper()}"


def _calculate_progress(
    estimated_distance: float | None,
    distance_remaining: float | None,
) -> float | None:
    if estimated_distance and distance_remaining is not None and estimated_distance > 0:
        covered = estimated_distance - distance_remaining
        return round(max(0, min(100, (covered / estimated_distance) * 100)), 1)
    return None


def _calculate_elapsed_minutes(started_at) -> float | None:
    if started_at:
        delta = utc_now() - started_at
        return round(delta.total_seconds() / 60, 1)
    return None


def _derive_trip_status(eta_minutes: float | None, session_status: str) -> str:
    if session_status == TrackingSessionStatus.COMPLETED:
        return "completed"
    if eta_minutes is not None and eta_minutes <= 5:
        return "arriving"
    return "transit"


def _extract_medical_alerts(ride_data: dict) -> list[str]:
    alerts = []
    ride_type = ride_data.get("ride_type")
    if ride_type and ride_type != "standard":
        alerts.append(ride_type.replace("_", " ").title())

    mobility = ride_data.get("mobility_level")
    if mobility and mobility != "ambulatory":
        alerts.append(f"Mobility: {mobility.replace('_', ' ').title()}")

    instructions = ride_data.get("special_instructions")
    if instructions:
        alerts.append("Special Instructions")

    return alerts
