import logging
from uuid import UUID

from app.clients.auth_service_client import AuthServiceClient
from app.clients.ride_service_client import RideServiceClient
from app.repositories.driver_repo import DriverRepository
from app.repositories.fleet_repo import FleetRepository
from app.repositories.user_repo import UserRepository
from app.schemas.caregiver import (
    CaregiverAssignment,
    CaregiverCertification,
    CaregiverDetailResponse,
    CaregiverKPIs,
    CaregiverPersonalInfo,
    CaregiverProfileCard,
    CaregiverRating,
    CaregiverRosterRow,
)
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.enums import CaregiverSpecialty

logger = logging.getLogger(__name__)


class CaregiverService:
    def __init__(
        self,
        driver_repo: DriverRepository,
        user_repo: UserRepository,
        fleet_repo: FleetRepository,
        auth_client: AuthServiceClient,
        ride_client: RideServiceClient,
        publisher: EventPublisher,
    ):
        self.driver_repo = driver_repo
        self.user_repo = user_repo
        self.fleet_repo = fleet_repo
        self.auth_client = auth_client
        self.ride_client = ride_client
        self.publisher = publisher

    async def get_kpis(self) -> CaregiverKPIs:
        """Get caregiver KPI cards."""
        # Get all drivers with specialty (caregivers)
        caregivers = await self.driver_repo.get_all_with_specialty()

        total = len(caregivers)
        available = sum(1 for c in caregivers if c.account_status == "active" and not c.is_online)
        on_assignment = sum(1 for c in caregivers if c.is_online)

        # Calculate average rating from ride service
        if caregivers:
            driver_ids = [c.user_id for c in caregivers]
            ratings_data = await self.ride_client.get_batch_driver_ratings(driver_ids)
            ratings = [r["avg_rating"] for r in ratings_data if r.get("avg_rating")]
            avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0.0
        else:
            avg_rating = 0.0

        return CaregiverKPIs(
            total_caregivers=total,
            available_now=available,
            on_assignment=on_assignment,
            avg_rating=avg_rating,
        )

    async def list_caregivers(
        self,
        specialty: str | None = None,
        status: str | None = None,
        search: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[CaregiverRosterRow], int]:
        """List caregivers with filters."""
        caregivers = await self.driver_repo.get_all_with_specialty()

        # Filter
        filtered = []
        for c in caregivers:
            # Specialty filter
            if specialty and c.specialty != specialty:
                continue

            # Status filter (available, on_assignment, active, suspended)
            if status:
                if status == "available" and (c.account_status != "active" or c.is_online):
                    continue
                if status == "on_assignment" and not c.is_online:
                    continue
                if status in ["active", "suspended", "pending"] and c.account_status != status:
                    continue

            # Get user details for search
            user = await self.user_repo.get_by_id(c.user_id)
            if not user:
                continue

            full_name = f"{user.first_name} {user.last_name}"

            # Search filter
            if search:
                search_lower = search.lower()
                searchable = f"{full_name} {c.specialty or ''}".lower()
                if search_lower not in searchable:
                    continue

            filtered.append((c, user))

        total = len(filtered)

        # Paginate
        offset = (page - 1) * limit
        paginated = filtered[offset : offset + limit]

        # Build response
        rows = []
        for driver_profile, user in paginated:
            full_name = f"{user.first_name} {user.last_name}"
            location = f"{driver_profile.city}, {driver_profile.province}" if driver_profile.city and driver_profile.province else None

            # Get certifications count (documents)
            # TODO: Implement document repo query
            certifications = []

            # Get ratings from ride service
            ratings_data = await self.ride_client.get_driver_ratings(driver_profile.user_id)
            avg_rating = ratings_data.get("avg_rating") if ratings_data else None

            # Get assignment count
            stats = await self.ride_client.get_driver_stats(driver_profile.user_id)
            assignments = stats.get("total_rides", 0) if stats else 0

            # Determine status
            status_str = "on_assignment" if driver_profile.is_online else "available"

            rows.append(
                CaregiverRosterRow(
                    caregiver_id=user.id,
                    driver_profile_id=driver_profile.id,
                    full_name=full_name,
                    avatar_url=user.avatar_url,
                    specialty=driver_profile.specialty or "",
                    certifications=certifications,
                    capabilities=driver_profile.service_capabilities or [],
                    status=status_str,
                    rating=avg_rating,
                    assignments=assignments,
                    location=location,
                    account_status=driver_profile.account_status or "active",
                )
            )

        return rows, total

    async def get_caregiver_profiles(
        self,
        specialty: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[CaregiverProfileCard], int]:
        """Get caregiver profile cards."""
        caregivers = await self.driver_repo.get_all_with_specialty()

        # Filter by specialty if provided
        if specialty:
            caregivers = [c for c in caregivers if c.specialty == specialty]

        total = len(caregivers)
        offset = (page - 1) * limit
        paginated = caregivers[offset : offset + limit]

        cards = []
        for driver_profile in paginated:
            user = await self.user_repo.get_by_id(driver_profile.user_id)
            if not user:
                continue

            full_name = f"{user.first_name} {user.last_name}"
            location = f"{driver_profile.city}, {driver_profile.province}" if driver_profile.city and driver_profile.province else None

            # Get ratings
            ratings_data = await self.ride_client.get_driver_ratings(driver_profile.user_id)
            avg_rating = ratings_data.get("avg_rating") if ratings_data else None

            # Get assignments
            stats = await self.ride_client.get_driver_stats(driver_profile.user_id)
            assignments = stats.get("total_rides", 0) if stats else 0

            cards.append(
                CaregiverProfileCard(
                    caregiver_id=user.id,
                    driver_profile_id=driver_profile.id,
                    full_name=full_name,
                    avatar_url=user.avatar_url,
                    specialty=driver_profile.specialty or "",
                    phone=user.phone,
                    location=location,
                    capabilities=driver_profile.service_capabilities or [],
                    rating=avg_rating,
                    assignments=assignments,
                    joined=user.created_at,
                )
            )

        return cards, total

    async def create_caregiver(
        self,
        first_name: str,
        last_name: str,
        email: str,
        phone: str,
        specialty: str,
        city: str | None,
        province: str | None,
        capabilities: list[str] | None,
        fleet_id: UUID | None,
        admin_id: UUID,
    ) -> dict:
        """Create a new caregiver (driver with specialty)."""
        # Validate specialty
        if specialty not in [s.value for s in CaregiverSpecialty]:
            raise ValueError(f"Invalid specialty: {specialty}")

        # Create auth credential via auth-service
        credential_data = await self.auth_client.create_driver_credential(
            email=email,
            first_name=first_name,
            last_name=last_name,
        )
        user_id = UUID(credential_data["user_id"])

        # Create user record
        user = await self.user_repo.create(
            id=user_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role="DRIVER",
        )

        # Create driver profile with specialty
        from app.models.driver_profile import DriverProfile

        driver_profile = DriverProfile(
            user_id=user_id,
            business_id=fleet_id,
            specialty=specialty,
            account_status="active",
            service_capabilities=capabilities,
            city=city,
            province=province,
        )
        driver_profile = await self.driver_repo.create(driver_profile)

        # Publish event
        await self.publisher.publish(
            exchange_name=Exchanges.USERS,
            routing_key=RoutingKeys.DRIVER_ACCOUNT_CREATED,
            payload={
                "user_id": str(user_id),
                "driver_profile_id": str(driver_profile.id),
                "specialty": specialty,
                "created_by": str(admin_id),
            },
        )

        return {
            "caregiver_id": user_id,
            "driver_profile_id": driver_profile.id,
            "full_name": f"{first_name} {last_name}",
            "specialty": specialty,
        }

    async def get_caregiver_detail(self, caregiver_id: UUID) -> CaregiverDetailResponse:
        """Get detailed caregiver information with tabs."""
        user = await self.user_repo.get_by_id(caregiver_id)
        if not user:
            raise ValueError("Caregiver not found")

        driver_profile = await self.driver_repo.get_by_user_id(caregiver_id)
        if not driver_profile or not driver_profile.specialty:
            raise ValueError("Not a caregiver")

        # Personal info
        personal_info = CaregiverPersonalInfo(
            full_name=f"{user.first_name} {user.last_name}",
            phone=user.phone,
            email=user.email,
            specialty=driver_profile.specialty,
            city=driver_profile.city,
            province=driver_profile.province,
            joined=user.created_at,
            languages=[],  # TODO: Add languages field to model
            capabilities=driver_profile.service_capabilities or [],
        )

        # Certifications (from documents)
        # TODO: Fetch from document repository
        certifications = [
            CaregiverCertification(name=driver_profile.specialty, status="active", expiry_date=None),
        ]

        # Assignments (from ride service)
        rides_data = await self.ride_client.get_driver_rides(caregiver_id, limit=10)
        assignments = []
        if rides_data:
            for ride in rides_data.get("rides", []):
                assignments.append(
                    CaregiverAssignment(
                        assignment_id=ride.get("id", ""),
                        patient_name=ride.get("rider_name", ""),
                        route=f"{ride.get('pickup_address', '')} → {ride.get('dropoff_address', '')}",
                        date=ride.get("scheduled_time", ""),
                        duration=ride.get("duration", ""),
                        status=ride.get("status", ""),
                    )
                )

        # Ratings (from ride service)
        ratings_data = await self.ride_client.get_driver_ratings(caregiver_id)
        ratings = []
        if ratings_data and ratings_data.get("reviews"):
            for review in ratings_data["reviews"]:
                ratings.append(
                    CaregiverRating(
                        patient_name=review.get("rider_name", ""),
                        rating=review.get("rating", 0),
                        review=review.get("comment"),
                        date=review.get("created_at", ""),
                    )
                )

        # Stats
        stats = await self.ride_client.get_driver_stats(caregiver_id)
        total_assignments = stats.get("total_rides", 0) if stats else 0
        avg_rating = ratings_data.get("avg_rating") if ratings_data else None

        return CaregiverDetailResponse(
            caregiver_id=user.id,
            driver_profile_id=driver_profile.id,
            personal_info=personal_info,
            certifications=certifications,
            assignments=assignments,
            ratings=ratings,
            total_assignments=total_assignments,
            avg_rating=avg_rating,
        )

    async def update_caregiver(
        self,
        caregiver_id: UUID,
        first_name: str | None,
        last_name: str | None,
        email: str | None,
        phone: str | None,
        specialty: str | None,
        city: str | None,
        province: str | None,
        capabilities: list[str] | None,
        fleet_id: UUID | None,
        admin_id: UUID,
    ) -> dict:
        """Update caregiver information."""
        user = await self.user_repo.get_by_id(caregiver_id)
        if not user:
            raise ValueError("Caregiver not found")

        driver_profile = await self.driver_repo.get_by_user_id(caregiver_id)
        if not driver_profile:
            raise ValueError("Driver profile not found")

        # Update user
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        if email:
            user.email = email
        if phone:
            user.phone = phone
        await self.user_repo.update(user)

        # Update driver profile
        if specialty:
            driver_profile.specialty = specialty
        if city:
            driver_profile.city = city
        if province:
            driver_profile.province = province
        if capabilities is not None:
            driver_profile.service_capabilities = capabilities
        if fleet_id:
            driver_profile.business_id = fleet_id

        await self.driver_repo.update(driver_profile)

        # Publish event
        await self.publisher.publish(
            exchange_name=Exchanges.USERS,
            routing_key=RoutingKeys.DRIVER_PROFILE_UPDATED,
            payload={
                "user_id": str(caregiver_id),
                "driver_profile_id": str(driver_profile.id),
                "updated_by": str(admin_id),
            },
        )

        return {
            "caregiver_id": caregiver_id,
            "driver_profile_id": driver_profile.id,
            "full_name": f"{user.first_name} {user.last_name}",
            "specialty": driver_profile.specialty,
        }
