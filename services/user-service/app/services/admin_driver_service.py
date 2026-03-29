import asyncio
import logging
import secrets
from datetime import timedelta
from uuid import UUID

from app.clients.auth_service_client import AuthServiceClient
from app.clients.ride_service_client import RideServiceClient
from app.config import settings
from app.models.driver_invitation import DriverInvitation
from app.repositories.admin_driver_repo import AdminDriverRepository
from app.repositories.fleet_repo import FleetRepository
from app.repositories.invitation_repo import InvitationRepository
from app.schemas.admin_driver import (
    AdminDriverDetailResponse,
    AdminDriverDocumentKPIs,
    AdminDriverDocumentListItem,
    AdminDriverDocumentOverview,
    AdminDriverKPIs,
    AdminDriverListItem,
    AdminDriverListResponse,
    AdminDriverRatingItem,
    AdminDriverStatusOverview,
    AdminDriverTripStats,
    CreateDriverRequest,
    DriverDocumentSummary,
    DriverStatusItem,
    DriverStatusKPIs,
    DriverStatusSection,
    SuspensionLogItem,
    UpdateDriverRequest,
)
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher
from mediride_common.events.schemas import DriverInviteSentPayload
from mediride_common.exceptions import ConflictError, NotFoundError, ValidationError
from mediride_common.utils import utc_now

logger = logging.getLogger(__name__)


class AdminDriverService:
    def __init__(
        self,
        repo: AdminDriverRepository,
        publisher: EventPublisher,
        auth_client: AuthServiceClient,
        ride_client: RideServiceClient,
        invitation_repo: InvitationRepository | None = None,
        fleet_repo: FleetRepository | None = None,
    ):
        self.repo = repo
        self.publisher = publisher
        self.auth_client = auth_client
        self.ride_client = ride_client
        self.invitation_repo = invitation_repo
        self.fleet_repo = fleet_repo

    async def get_driver_kpis(self, fleet_id: UUID | None = None) -> AdminDriverKPIs:
        data = await self.repo.get_driver_kpis(fleet_id)
        return AdminDriverKPIs(**data)

    async def list_drivers(
        self,
        search: str | None = None,
        fleet_id: UUID | None = None,
        account_status: str | None = None,
        is_online: bool | None = None,
        sort_by: str = "created_at",
        page: int = 1,
        limit: int = 20,
    ) -> AdminDriverListResponse:
        offset = (page - 1) * limit
        kpis = await self.get_driver_kpis(fleet_id)

        drivers_data, total = await self.repo.list_drivers_for_admin(
            search=search,
            fleet_id=fleet_id,
            account_status=account_status,
            is_online=is_online,
            sort_by=sort_by,
            offset=offset,
            limit=limit,
        )

        # Enrich with document status
        drivers = []
        for d in drivers_data:
            docs = await self.repo.get_driver_documents(d["user_id"])
            doc_status = self.repo._compute_document_status(docs)
            drivers.append(
                AdminDriverListItem(
                    **d,
                    document_status=doc_status,
                )
            )

        return AdminDriverListResponse(
            kpis=kpis,
            drivers=drivers,
            total=total,
            page=page,
            limit=limit,
            total_pages=(total + limit - 1) // limit,
        )

    async def get_driver_detail(self, driver_user_id: UUID) -> AdminDriverDetailResponse:
        detail = await self.repo.get_driver_detail(driver_user_id)
        if not detail:
            raise NotFoundError("Driver not found")

        # Get documents
        docs = await self.repo.get_driver_documents(driver_user_id)
        documents = [DriverDocumentSummary(**d) for d in docs]

        # Get suspension history
        suspension_logs = await self.repo.get_suspension_history(driver_user_id)
        suspension_history = [SuspensionLogItem(**log) for log in suspension_logs]

        # Get trip stats and ratings from ride-service (parallel)
        trip_stats_data, ratings_data = await asyncio.gather(
            self.ride_client.get_driver_stats(driver_user_id),
            self.ride_client.get_driver_ratings(driver_user_id),
        )

        trip_stats = AdminDriverTripStats()
        if trip_stats_data:
            trip_stats = AdminDriverTripStats(
                total_trips=trip_stats_data.get("total_trips", 0),
                hours_online=trip_stats_data.get("hours_online", 0.0),
                average_earnings=trip_stats_data.get("average_earnings", 0.0),
            )

        ratings = []
        if ratings_data:
            for r in ratings_data.get("ratings", []):
                ratings.append(
                    AdminDriverRatingItem(
                        ride_id=r["ride_id"],
                        rated_by_user_id=r.get("rated_by_user_id"),
                        rating=r["rating"],
                        comment=r.get("comment"),
                        created_at=r.get("created_at"),
                    )
                )

        return AdminDriverDetailResponse(
            **detail,
            trip_stats=trip_stats,
            documents=documents,
            ratings=ratings,
            suspension_history=suspension_history,
        )

    async def create_driver(
        self, admin_id: UUID, request: CreateDriverRequest
    ) -> AdminDriverDetailResponse:
        # Create credential in auth-service
        try:
            cred_result = await self.auth_client.create_driver_credential(
                email=request.email,
                phone=request.phone,
                password=request.password,
                business_id=request.fleet_id,
            )
        except RuntimeError as e:
            raise ValidationError(str(e))

        user_id = UUID(cred_result["user_id"])

        # Create user record
        await self.repo.create_user(
            id=user_id,
            email=request.email,
            phone=request.phone,
            first_name=request.first_name,
            last_name=request.last_name,
            role="driver",
            business_id=request.fleet_id,
            date_of_birth=request.date_of_birth,
        )

        # Create driver profile
        await self.repo.create_driver_profile(
            user_id=user_id,
            business_id=request.fleet_id,
            license_number=request.license_number,
            license_expiry=request.license_expiry,
            vehicle_type=request.vehicle_type,
            vehicle_make=request.vehicle_make,
            vehicle_model=request.vehicle_model,
            vehicle_year=request.vehicle_year,
            vehicle_plate=request.vehicle_plate,
            vehicle_color=request.vehicle_color,
            service_capabilities=request.service_capabilities,
            specialty=request.specialty,
            date_of_birth=request.date_of_birth,
            emergency_contact_name=request.emergency_contact_name,
            emergency_contact_phone=request.emergency_contact_phone,
            address=request.address,
            city=request.city,
            province=request.province,
            postal_code=request.postal_code,
            account_status="pending",
        )

        await self.publisher.publish(
            Exchanges.USERS,
            RoutingKeys.DRIVER_ACCOUNT_CREATED,
            {
                "driver_id": str(user_id),
                "email": request.email,
                "fleet_id": str(request.fleet_id),
                "created_by": str(admin_id),
            },
        )

        # Create invitation and send email to driver
        invite_token = None
        if self.invitation_repo and self.fleet_repo:
            try:
                fleet = await self.fleet_repo.get_by_id(request.fleet_id)
                fleet_name = fleet.name if fleet else "MediRide"

                token = secrets.token_urlsafe(32)
                invitation = DriverInvitation(
                    business_id=request.fleet_id,
                    email=request.email,
                    invited_by=admin_id,
                    token=token,
                    expires_at=utc_now() + timedelta(days=settings.INVITE_TOKEN_EXPIRE_DAYS),
                )
                await self.invitation_repo.create(invitation)

                await self.publisher.publish(
                    Exchanges.AUTH,
                    RoutingKeys.DRIVER_INVITE_SENT,
                    DriverInviteSentPayload(
                        invitation_id=invitation.id,
                        business_id=request.fleet_id,
                        fleet_name=fleet_name,
                        email=request.email,
                        invite_token=token,
                    ).model_dump(mode="json"),
                )

                invite_token = token
                logger.info(f"Driver invitation created for {request.email}")
            except Exception as e:
                logger.warning(f"Failed to create driver invitation: {e}")

        logger.info(f"Admin created driver: {user_id}")
        detail = await self.get_driver_detail(user_id)
        detail.invite_token = invite_token
        return detail

    async def update_driver(
        self, driver_user_id: UUID, request: UpdateDriverRequest
    ) -> AdminDriverDetailResponse:
        detail = await self.repo.get_driver_detail(driver_user_id)
        if not detail:
            raise NotFoundError("Driver not found")

        update_data = request.model_dump(exclude_unset=True)

        # Split user fields vs driver profile fields
        user_fields = {}
        driver_fields = {}
        user_field_names = {"first_name", "last_name", "phone"}

        for key, value in update_data.items():
            if key in user_field_names:
                user_fields[key] = value
            elif key == "fleet_id":
                driver_fields["business_id"] = value
            else:
                driver_fields[key] = value

        if user_fields:
            await self.repo.update_user(driver_user_id, **user_fields)
        if driver_fields:
            await self.repo.update_driver_profile(driver_user_id, **driver_fields)

        await self.publisher.publish(
            Exchanges.USERS,
            RoutingKeys.DRIVER_PROFILE_UPDATED,
            {"driver_id": str(driver_user_id)},
        )

        logger.info(f"Admin updated driver: {driver_user_id}")
        return await self.get_driver_detail(driver_user_id)

    async def approve_driver(self, driver_user_id: UUID, admin_id: UUID) -> AdminDriverDetailResponse:
        detail = await self.repo.get_driver_detail(driver_user_id)
        if not detail:
            raise NotFoundError("Driver not found")

        await self.repo.update_driver_profile(
            driver_user_id,
            is_approved=True,
            account_status="active",
            background_check_status="approved",
            approved_at=utc_now(),
        )

        await self.repo.create_suspension_log(
            driver_id=driver_user_id,
            action="approved",
            reason=None,
            performed_by=admin_id,
        )

        await self.publisher.publish(
            Exchanges.USERS,
            RoutingKeys.DRIVER_APPROVED,
            {"driver_id": str(driver_user_id), "approved_by": str(admin_id)},
        )

        logger.info(f"Admin approved driver: {driver_user_id}")
        return await self.get_driver_detail(driver_user_id)

    async def suspend_driver(
        self, driver_user_id: UUID, reason: str, admin_id: UUID
    ) -> AdminDriverDetailResponse:
        detail = await self.repo.get_driver_detail(driver_user_id)
        if not detail:
            raise NotFoundError("Driver not found")
        if detail["account_status"] == "suspended":
            raise ValidationError("Driver is already suspended")

        now = utc_now()
        await self.repo.update_driver_profile(
            driver_user_id,
            account_status="suspended",
            is_approved=False,
            is_online=False,
            suspension_reason=reason,
            suspended_at=now,
            suspended_by=admin_id,
        )

        await self.repo.create_suspension_log(
            driver_id=driver_user_id,
            action="suspended",
            reason=reason,
            performed_by=admin_id,
        )

        # Deactivate auth credential
        await self.auth_client.deactivate_account(driver_user_id)

        await self.publisher.publish(
            Exchanges.USERS,
            RoutingKeys.DRIVER_SUSPENDED,
            {
                "driver_id": str(driver_user_id),
                "reason": reason,
                "suspended_by": str(admin_id),
            },
        )

        logger.info(f"Admin suspended driver: {driver_user_id}")
        return await self.get_driver_detail(driver_user_id)

    async def reactivate_driver(
        self, driver_user_id: UUID, admin_id: UUID
    ) -> AdminDriverDetailResponse:
        detail = await self.repo.get_driver_detail(driver_user_id)
        if not detail:
            raise NotFoundError("Driver not found")
        if detail["account_status"] not in ("suspended", "deactivated"):
            raise ValidationError("Driver is not suspended or deactivated")

        await self.repo.update_driver_profile(
            driver_user_id,
            account_status="active",
            is_approved=True,
            suspension_reason=None,
            suspended_at=None,
            suspended_by=None,
            deactivated_at=None,
        )

        await self.repo.create_suspension_log(
            driver_id=driver_user_id,
            action="reactivated",
            reason=None,
            performed_by=admin_id,
        )

        # Reactivate auth credential
        await self.auth_client.reactivate_account(driver_user_id)

        await self.publisher.publish(
            Exchanges.USERS,
            RoutingKeys.DRIVER_REACTIVATED,
            {"driver_id": str(driver_user_id), "reactivated_by": str(admin_id)},
        )

        logger.info(f"Admin reactivated driver: {driver_user_id}")
        return await self.get_driver_detail(driver_user_id)

    async def deactivate_driver(
        self, driver_user_id: UUID, admin_id: UUID
    ) -> AdminDriverDetailResponse:
        detail = await self.repo.get_driver_detail(driver_user_id)
        if not detail:
            raise NotFoundError("Driver not found")

        await self.repo.update_driver_profile(
            driver_user_id,
            account_status="deactivated",
            is_approved=False,
            is_online=False,
            deactivated_at=utc_now(),
        )

        await self.repo.create_suspension_log(
            driver_id=driver_user_id,
            action="deactivated",
            reason=None,
            performed_by=admin_id,
        )

        await self.auth_client.deactivate_account(driver_user_id)

        await self.publisher.publish(
            Exchanges.USERS,
            RoutingKeys.DRIVER_DEACTIVATED,
            {"driver_id": str(driver_user_id), "deactivated_by": str(admin_id)},
        )

        logger.info(f"Admin deactivated driver: {driver_user_id}")
        return await self.get_driver_detail(driver_user_id)

    async def reassign_fleet(
        self, driver_user_id: UUID, fleet_id: UUID
    ) -> AdminDriverDetailResponse:
        detail = await self.repo.get_driver_detail(driver_user_id)
        if not detail:
            raise NotFoundError("Driver not found")

        await self.repo.update_driver_profile(driver_user_id, business_id=fleet_id)
        await self.repo.update_user(driver_user_id, business_id=fleet_id)

        logger.info(f"Admin reassigned driver {driver_user_id} to fleet {fleet_id}")
        return await self.get_driver_detail(driver_user_id)

    async def get_document_overview(
        self,
        search: str | None = None,
        status_filter: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> AdminDriverDocumentOverview:
        offset = (page - 1) * limit
        kpis_data = await self.repo.get_document_kpis()
        kpis = AdminDriverDocumentKPIs(**kpis_data)

        drivers_data, total = await self.repo.list_drivers_with_document_status(
            search=search,
            status_filter=status_filter,
            offset=offset,
            limit=limit,
        )

        drivers = [
            AdminDriverDocumentListItem(
                user_id=d["user_id"],
                first_name=d["first_name"],
                last_name=d["last_name"],
                email=d["email"],
                fleet_name=d["fleet_name"],
                documents=[DriverDocumentSummary(**doc) for doc in d["documents"]],
                document_status=d["document_status"],
            )
            for d in drivers_data
        ]

        return AdminDriverDocumentOverview(
            kpis=kpis,
            drivers=drivers,
            total=total,
            page=page,
            limit=limit,
            total_pages=(total + limit - 1) // limit,
        )

    async def get_driver_status_overview(self) -> AdminDriverStatusOverview:
        kpis_data = await self.repo.get_status_kpis()
        kpis = DriverStatusKPIs(**kpis_data)

        sections = []
        for status in ["active", "suspended", "pending", "deactivated"]:
            drivers_data = await self.repo.get_drivers_by_status(status)
            drivers = [DriverStatusItem(**d) for d in drivers_data]
            count = kpis_data.get(f"{status}_count", 0)
            sections.append(
                DriverStatusSection(status=status, count=count, drivers=drivers)
            )

        return AdminDriverStatusOverview(kpis=kpis, sections=sections)
