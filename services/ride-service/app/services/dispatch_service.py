"""Dispatch service for auto-assignment and dispatch center operations."""
import logging
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.clients.user_service_client import UserServiceClient

from app.repositories.dispatch_repo import DispatchRepository
from app.schemas.dispatch import (
    AutoAssignmentResult,
    AutoDispatchSettings,
    AvailableDriverItem,
    DispatchDashboardResponse,
    DispatchKPIs,
    DispatchPriorityRules,
    DistanceMatchingLogic,
    FallbackBehavior,
    TriggerAutoDispatchResponse,
    UnassignedRideItem,
    UpdateAutoDispatchSettingsRequest,
)
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher

logger = logging.getLogger(__name__)


class DispatchService:
    def __init__(
        self,
        repo: DispatchRepository,
        user_service_client: "UserServiceClient",
        publisher: EventPublisher,
    ):
        self.repo = repo
        self.user_client = user_service_client
        self.publisher = publisher

    async def get_dispatch_dashboard(self) -> DispatchDashboardResponse:
        """Get dispatch center dashboard with KPIs, unassigned rides, and available drivers."""
        # Get KPIs
        kpis_data = await self.repo.get_dispatch_kpis()

        # Get unassigned rides
        rides, _ = await self.repo.get_unassigned_rides(limit=50)

        # Fetch rider names and roles in batch
        rider_ids = [r.rider_id for r in rides]
        rider_details = {}
        if rider_ids:
            try:
                riders_data = await self.user_client.batch_get_users(rider_ids)
                rider_details = {
                    UUID(u["id"]): {
                        "name": f"{u.get('first_name', '')} {u.get('last_name', '')}".strip(),
                        "role": u.get("role"),
                    }
                    for u in riders_data if u.get("id")
                }
            except Exception as e:
                logger.error(f"Failed to fetch rider names: {e}")

        unassigned_rides = []
        for r in rides:
            rider_info = rider_details.get(r.rider_id, {})
            patient_name = None
            if r.passenger_first_name or r.passenger_last_name:
                patient_name = f"{r.passenger_first_name or ''} {r.passenger_last_name or ''}".strip()

            unassigned_rides.append(
                UnassignedRideItem(
                    ride_id=r.id,
                    booking_number=f"BK-{str(r.id)[:8].upper()}",
                    rider_name=rider_info.get("name", f"Rider {str(r.rider_id)[:8]}"),
                    ride_type=r.ride_type,
                    pickup_address=r.pickup_address,
                    destination_address=r.destination_address,
                    scheduled_at=r.scheduled_at,
                    distance_km=float(r.estimated_distance_miles) * 1.60934
                    if r.estimated_distance_miles
                    else None,
                    estimated_fare=float(r.estimated_fare) if r.estimated_fare else None,
                    patient_name=patient_name,
                    rider_role=rider_info.get("role"),
                    special_requirements=self._extract_special_requirements(r),
                    assigned_status=None,
                )
            )

        # Get available drivers from user-service
        available_drivers_data = await self.user_client.get_available_drivers()
        available_drivers = []
        if available_drivers_data:
            for d in available_drivers_data:
                available_drivers.append(
                    AvailableDriverItem(
                        driver_id=UUID(d["user_id"]),
                        driver_name=f"{d.get('first_name', '')} {d.get('last_name', '')}".strip(),
                        vehicle_type=d.get("vehicle_type") or "Unknown",
                        vehicle_info=f"{d.get('vehicle_make', '')} {d.get('vehicle_model', '')} - {d.get('vehicle_year', '')}".strip(),
                        rating=d.get("rating", 5.0),
                        total_trips=d.get("total_trips", 0),
                        distance_from_pickup=None,  # Requires geolocation calculation
                        eta_minutes=None,
                        specialty=d.get("specialty"),
                        fleet_name=d.get("fleet_name"),
                    )
                )

        # Update KPI with available drivers count
        kpis_data["available_drivers"] = len(available_drivers)
        kpis = DispatchKPIs(**kpis_data)

        return DispatchDashboardResponse(
            kpis=kpis,
            unassigned_rides=unassigned_rides,
            available_drivers=available_drivers,
        )

    def _extract_special_requirements(self, ride) -> list[str]:
        """Extract special requirements from ride."""
        requirements = []
        if ride.mobility_level and ride.mobility_level != "ambulatory":
            requirements.append(ride.mobility_level.replace("_", " ").title())
        if ride.assistance_level and ride.assistance_level != "none":
            requirements.append(f"{ride.assistance_level.replace('_', ' ').title()} Assistance")
        if ride.trip_type and "care" in ride.trip_type.lower():
            requirements.append("Care Assistant")
        return requirements

    async def get_unassigned_rides(
        self, page: int = 1, limit: int = 50
    ) -> dict:
        """Get paginated unassigned rides."""
        offset = (page - 1) * limit
        rides, total = await self.repo.get_unassigned_rides(limit=limit, offset=offset)

        # Fetch rider names in batch
        rider_ids = [r.rider_id for r in rides]
        rider_details = {}
        if rider_ids:
            try:
                riders_data = await self.user_client.batch_get_users(rider_ids)
                rider_details = {
                    UUID(u["id"]): {
                        "name": f"{u.get('first_name', '')} {u.get('last_name', '')}".strip(),
                        "role": u.get("role"),
                    }
                    for u in riders_data if u.get("id")
                }
            except Exception as e:
                logger.error(f"Failed to fetch rider names: {e}")

        items = []
        for r in rides:
            rider_info = rider_details.get(r.rider_id, {})
            patient_name = None
            if r.passenger_first_name or r.passenger_last_name:
                patient_name = f"{r.passenger_first_name or ''} {r.passenger_last_name or ''}".strip()

            items.append(
                UnassignedRideItem(
                    ride_id=r.id,
                    booking_number=f"BK-{str(r.id)[:8].upper()}",
                    rider_name=rider_info.get("name", f"Rider {str(r.rider_id)[:8]}"),
                    ride_type=r.ride_type,
                    pickup_address=r.pickup_address,
                    destination_address=r.destination_address,
                    scheduled_at=r.scheduled_at,
                    distance_km=float(r.estimated_distance_miles) * 1.60934
                    if r.estimated_distance_miles
                    else None,
                    estimated_fare=float(r.estimated_fare) if r.estimated_fare else None,
                    patient_name=patient_name,
                    rider_role=rider_info.get("role"),
                    special_requirements=self._extract_special_requirements(r),
                )
            )

        return {
            "rides": items,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit,
        }

    async def get_available_drivers(self) -> list[AvailableDriverItem]:
        """Get list of available drivers from user-service."""
        drivers_data = await self.user_client.get_available_drivers()
        if not drivers_data:
            return []

        available_drivers = []
        for d in drivers_data:
            available_drivers.append(
                AvailableDriverItem(
                    driver_id=UUID(d["user_id"]),
                    driver_name=f"{d.get('first_name', '')} {d.get('last_name', '')}".strip(),
                    vehicle_type=d.get("vehicle_type") or "Unknown",
                    vehicle_info=f"{d.get('vehicle_make', '')} {d.get('vehicle_model', '')} - {d.get('vehicle_year', '')}".strip(),
                    rating=d.get("rating", 5.0),
                    total_trips=d.get("total_trips", 0),
                    specialty=d.get("specialty"),
                    fleet_name=d.get("fleet_name"),
                )
            )
        return available_drivers

    async def get_active_trips(self) -> list[dict]:
        """
        Get all active trips with enriched data.
        Returns trips with driver_arrived or in_progress status.
        """
        rides = await self.repo.get_active_trips()
        if not rides:
            return []

        # Collect unique rider and driver IDs
        rider_ids = [r.rider_id for r in rides]
        driver_ids = [r.driver_id for r in rides if r.driver_id]

        # Fetch user details in batch
        rider_details = {}
        driver_details = {}

        try:
            if rider_ids:
                riders_data = await self.user_client.batch_get_users(rider_ids)
                rider_details = {
                    UUID(u["id"]): u for u in riders_data if u.get("id")
                }
        except Exception as e:
            logger.error(f"Failed to fetch rider details: {e}")


        try:
            if driver_ids:
                drivers_data = await self.user_client.get_drivers_with_details(
                    driver_ids
                )
                driver_details = {
                    UUID(d["driver_id"]): d for d in drivers_data if d.get("driver_id")
                }
        except Exception as e:
            logger.error(f"Failed to fetch driver details: {e}")

        # Build response
        active_trips = []
        for ride in rides:
            rider = rider_details.get(ride.rider_id, {})
            driver = driver_details.get(ride.driver_id, {}) if ride.driver_id else {}

            rider_name = f"{rider.get('first_name', '')} {rider.get('last_name', '')}".strip() or "Unknown"
            driver_name = f"{driver.get('first_name', '')} {driver.get('last_name', '')}".strip() or "Unassigned"

            patient_name = None
            if ride.passenger_first_name or ride.passenger_last_name:
                patient_name = f"{ride.passenger_first_name or ''} {ride.passenger_last_name or ''}".strip()

            active_trips.append({
                "trip_id": str(ride.id),
                "booking_number": f"TR-{str(ride.id)[:8].upper()}",
                "rider_id": str(ride.rider_id),
                "rider_name": rider_name,
                "rider_role": rider.get("role"),
                "patient_name": patient_name,
                "driver_id": str(ride.driver_id) if ride.driver_id else None,
                "driver_name": driver_name,
                "driver_avatar": driver.get("avatar_url"),
                "status": ride.status,
                "ride_type": ride.ride_type,
                "pickup_address": ride.pickup_address,
                "destination_address": ride.destination_address,
                "scheduled_at": ride.scheduled_at.isoformat() if ride.scheduled_at else None,
                "pickup_at": ride.pickup_at.isoformat() if ride.pickup_at else None,
                "progress_percent": self._calculate_progress(ride),
                "eta_minutes": None,  # Will be updated by tracking-service
                "speed_mph": None,  # Will be updated by tracking-service
                "special_requirements": self._extract_special_requirements(ride),
            })

        return active_trips

    def _calculate_progress(self, ride) -> int:
        """Calculate trip progress percentage based on status."""
        status_progress = {
            "driver_arrived": 75,
            "in_progress": 85,
        }
        return status_progress.get(ride.status, 0)

    # --- Auto-Dispatch Settings ---

    async def get_dispatch_settings(self) -> AutoDispatchSettings:
        """Get current auto-dispatch settings."""
        settings = await self.repo.get_dispatch_settings()
        if not settings:
            # Create default settings
            settings = await self.repo.create_dispatch_settings(
                auto_dispatch_enabled=False,
                search_radius_km=5,
            )

        return AutoDispatchSettings(
            id=settings.id,
            auto_dispatch_enabled=settings.auto_dispatch_enabled,
            distance_matching=DistanceMatchingLogic(
                search_radius_km=settings.search_radius_km
            ),
            priority_rules=DispatchPriorityRules(**settings.priority_rules),
            fallback_behavior=FallbackBehavior(**settings.fallback_behavior),
            updated_at=settings.updated_at,
            updated_by=settings.updated_by,
        )

    async def update_dispatch_settings(
        self, admin_id: UUID, request: UpdateAutoDispatchSettingsRequest
    ) -> AutoDispatchSettings:
        """Update auto-dispatch settings."""
        settings = await self.repo.get_dispatch_settings()
        if not settings:
            # Create if doesn't exist
            settings = await self.repo.create_dispatch_settings(
                auto_dispatch_enabled=request.auto_dispatch_enabled,
                search_radius_km=request.distance_matching.search_radius_km,
                priority_rules=request.priority_rules.model_dump(),
                fallback_behavior=request.fallback_behavior.model_dump(),
                updated_by=admin_id,
            )
        else:
            # Update existing
            settings = await self.repo.update_dispatch_settings(
                settings.id,
                auto_dispatch_enabled=request.auto_dispatch_enabled,
                search_radius_km=request.distance_matching.search_radius_km,
                priority_rules=request.priority_rules.model_dump(),
                fallback_behavior=request.fallback_behavior.model_dump(),
                updated_by=admin_id,
            )

        return await self.get_dispatch_settings()

    # --- Auto-Dispatch Logic ---

    async def trigger_auto_dispatch(
        self, admin_id: UUID
    ) -> TriggerAutoDispatchResponse:
        """
        Trigger auto-dispatch for all eligible rides.
        Matches drivers to rides based on configured rules.
        """
        settings = await self.repo.get_dispatch_settings()
        if not settings or not settings.auto_dispatch_enabled:
            logger.warning("Auto-dispatch triggered but not enabled")
            return TriggerAutoDispatchResponse(
                total_rides=0, assigned_count=0, failed_count=0, results=[]
            )

        # Get rides eligible for auto-dispatch
        rides = await self.repo.get_rides_for_auto_dispatch(scheduled_window_hours=24)
        logger.info(f"Found {len(rides)} rides eligible for auto-dispatch")

        results = []
        assigned_count = 0
        failed_count = 0

        for ride in rides:
            result = await self._auto_assign_driver_to_ride(ride, settings)
            results.append(result)
            if result.assigned:
                assigned_count += 1
            else:
                failed_count += 1

        return TriggerAutoDispatchResponse(
            total_rides=len(rides),
            assigned_count=assigned_count,
            failed_count=failed_count,
            results=results,
        )

    async def _auto_assign_driver_to_ride(
        self, ride, settings
    ) -> AutoAssignmentResult:
        """Auto-assign a driver to a ride based on matching rules."""
        # Get available drivers
        available_drivers = await self.user_client.get_available_drivers()
        if not available_drivers:
            return AutoAssignmentResult(
                ride_id=ride.id,
                driver_id=None,
                assigned=False,
                reason="No available drivers",
            )

        drivers = available_drivers

        # Apply matching rules
        matched_driver = self._match_driver(ride, drivers, settings)
        if not matched_driver:
            return AutoAssignmentResult(
                ride_id=ride.id,
                driver_id=None,
                assigned=False,
                reason="No suitable driver found within criteria",
            )

        # Assign driver
        driver_id = UUID(matched_driver["user_id"])
        business_id = UUID(matched_driver["fleet_id"]) if matched_driver.get("fleet_id") else None

        updated_ride = await self.repo.assign_driver_to_ride(
            ride.id, driver_id, business_id
        )

        # Publish event
        await self.publisher.publish(
            Exchanges.RIDES,
            RoutingKeys.RIDE_DRIVER_ASSIGNED,
            {
                "ride_id": str(ride.id),
                "driver_id": str(driver_id),
                "business_id": str(business_id) if business_id else None,
                "assigned_via": "auto_dispatch",
            },
        )

        return AutoAssignmentResult(
            ride_id=ride.id,
            driver_id=driver_id,
            assigned=True,
            reason="Auto-assigned successfully",
        )

    def _match_driver(self, ride, drivers: list[dict], settings) -> dict | None:
        """
        Match best driver for a ride based on priority rules.
        Returns the best matched driver or None.
        """
        priority_rules = settings.priority_rules

        # Filter by vehicle type if enabled
        if priority_rules.get("match_vehicle_type", True):
            # Match ride_type to vehicle category
            drivers = [
                d
                for d in drivers
                if self._vehicle_matches_ride_type(
                    d.get("vehicle_type"), ride.ride_type
                )
            ]

        if not drivers:
            return None

        # Sort by priority rules
        if priority_rules.get("prioritize_by_rating", True):
            drivers = sorted(drivers, key=lambda d: d.get("rating", 0), reverse=True)

        # Return best match
        return drivers[0] if drivers else None

    def _vehicle_matches_ride_type(
        self, vehicle_type: str | None, ride_type: str
    ) -> bool:
        """Check if vehicle type matches ride type requirements."""
        if not vehicle_type:
            return True  # Accept if unknown

        vehicle_type = vehicle_type.lower()
        ride_type = ride_type.lower()

        # Mapping logic
        if "wheelchair" in ride_type or "wav" in ride_type:
            return "wav" in vehicle_type or "wheelchair" in vehicle_type
        if "stretcher" in ride_type:
            return "stretcher" in vehicle_type
        # Default: ambulatory rides can use any vehicle
        return True
