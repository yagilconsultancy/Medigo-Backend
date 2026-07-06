import asyncio
import logging
import secrets
from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from app.clients.auth_service_client import AuthServiceClient
from app.clients.ride_service_client import RideServiceClient
from app.config import settings
from app.models.driver_invitation import DriverInvitation
from app.repositories.admin_driver_repo import AdminDriverRepository
from app.repositories.fleet_repo import FleetRepository
from app.repositories.invitation_repo import InvitationRepository
from app.repositories.vehicle_repo import VehicleRepository

if TYPE_CHECKING:
    from fastapi import UploadFile

    from app.services.document_service import DocumentService
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
from mediride_common.events.schemas import (
    DriverEmailChangedPayload,
    DriverInviteSentPayload,
)
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
        vehicle_repo: VehicleRepository | None = None,
        document_service: "DocumentService | None" = None,
    ):
        self.repo = repo
        self.publisher = publisher
        self.auth_client = auth_client
        self.ride_client = ride_client
        self.invitation_repo = invitation_repo
        self.fleet_repo = fleet_repo
        self.vehicle_repo = vehicle_repo
        self.document_service = document_service

    async def get_driver_kpis(self, fleet_id: UUID | None = None) -> AdminDriverKPIs:
        # DB KPIs + ride-service dashboard stats in parallel
        data, dashboard_stats = await asyncio.gather(
            self.repo.get_driver_kpis(fleet_id),
            self.ride_client.get_driver_dashboard_stats(),
        )

        on_trip = 0
        available_now = data["online_count"]
        total_mileage = 0.0

        if dashboard_stats:
            on_trip = dashboard_stats.get("on_trip_count", 0)
            total_mileage = dashboard_stats.get("total_mileage_miles", 0.0)
            # Available = online but NOT on a trip
            on_trip_ids = set(dashboard_stats.get("on_trip_driver_ids", []))
            if on_trip_ids:
                online_on_trip = await self.repo.count_online_drivers_in_set(on_trip_ids)
                available_now = data["online_count"] - online_on_trip

        return AdminDriverKPIs(
            **data,
            available_now=available_now,
            on_trip=on_trip,
            total_mileage=total_mileage,
        )

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

        # Get trip stats, ratings (ride-service) and login active-state (auth) in parallel
        trip_stats_data, ratings_data, is_active = await asyncio.gather(
            self.ride_client.get_driver_stats(driver_user_id),
            self.ride_client.get_driver_ratings(driver_user_id),
            self.auth_client.get_is_active(driver_user_id),
        )

        # Deactivated login while the profile is otherwise active/pending => the driver
        # changed-email flow is awaiting the reactivation link (suspended/deactivated excluded).
        pending_reactivation = (
            is_active is False
            and detail.get("account_status") not in ("suspended", "deactivated")
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
            pending_reactivation=pending_reactivation,
            trip_stats=trip_stats,
            documents=documents,
            ratings=ratings,
            suspension_history=suspension_history,
        )

    async def create_driver(
        self,
        admin_id: UUID,
        request: CreateDriverRequest,
        documents: "dict[str, UploadFile] | None" = None,
    ) -> AdminDriverDetailResponse:
        # Use default password for driver credential
        default_password = settings.DEFAULT_DRIVER_PASSWORD

        # Create credential in auth-service
        try:
            cred_result = await self.auth_client.create_driver_credential(
                email=request.email,
                phone=request.phone,
                password=default_password,
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
            is_active=True,  # Auto-activate driver
        )

        # Create driver profile
        profile_data = {
            "user_id": user_id,
            "business_id": request.fleet_id,
            "license_number": request.license_number,
            "license_expiry": request.license_expiry,
            "medical_transport_certification": request.medical_transport_certification,
            "background_check_status": request.background_check_status,
            "service_capabilities": request.service_capabilities,
            "specialty": request.specialty,
            "date_of_birth": request.date_of_birth,
            "account_status": request.account_status,
            "is_approved": request.is_approved,
        }

        # Set approved_at timestamp if driver is being approved
        if request.is_approved:
            profile_data["approved_at"] = utc_now()

        await self.repo.create_driver_profile(**profile_data)

        # Assign vehicle if provided
        if request.vehicle_id and self.vehicle_repo:
            await self.vehicle_repo.update(
                request.vehicle_id, driver_profile_id=user_id
            )

        # Upload any documents attached to the create request
        if documents and self.document_service:
            for doc_type, upload in documents.items():
                try:
                    file_data = await upload.read()
                    if not file_data:
                        continue
                    document = await self.document_service.upload_document(
                        user_id=user_id,
                        document_type=doc_type,
                        file_data=file_data,
                        file_name=upload.filename or f"{doc_type}",
                        content_type=upload.content_type or "application/octet-stream",
                        business_id=request.fleet_id,
                    )
                    # Auto-approve documents uploaded during admin driver creation
                    await self.document_service.verify_document(
                        document_id=document.id,
                        admin_id=admin_id,
                        status="approved",
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to upload {doc_type} for driver {user_id}: {e}"
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

                token = secrets.token_urlsafe(5)
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
                        # email=request.email,
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

    async def resend_invitation(self, driver_user_id: UUID, admin_id: UUID) -> str:
        """Revoke any existing pending invitation and create a new one. Returns the new invite token."""
        detail = await self.repo.get_driver_detail(driver_user_id)
        if not detail:
            raise NotFoundError("Driver not found")

        if not self.invitation_repo or not self.fleet_repo:
            raise ValidationError("Invitation service not available")

        email = detail["email"]
        fleet_id = detail["fleet_id"]
        fleet_name = detail.get("fleet_name") or "MediRide"

        # Revoke any existing pending invitation for this email + fleet
        existing = await self.invitation_repo.get_by_email_and_fleet(email, fleet_id)
        if existing:
            await self.invitation_repo.revoke(existing.id)

        # Create new invitation
        token = secrets.token_urlsafe(5)
        invitation = DriverInvitation(
            business_id=fleet_id,
            email=email,
            invited_by=admin_id,
            token=token,
            expires_at=utc_now() + timedelta(days=settings.INVITE_TOKEN_EXPIRE_DAYS),
        )
        await self.invitation_repo.create(invitation)

        # Publish event to send email
        await self.publisher.publish(
            Exchanges.AUTH,
            RoutingKeys.DRIVER_INVITE_SENT,
            DriverInviteSentPayload(
                invitation_id=invitation.id,
                business_id=fleet_id,
                fleet_name=fleet_name,
                email=email,
                invite_token=token,
            ).model_dump(mode="json"),
        )

        logger.info(f"Resent invitation for driver {driver_user_id} to {email}")
        return token

    async def update_driver(
        self, driver_user_id: UUID, request: UpdateDriverRequest
    ) -> AdminDriverDetailResponse:
        detail = await self.repo.get_driver_detail(driver_user_id)
        if not detail:
            raise NotFoundError("Driver not found")

        update_data = request.model_dump(exclude_unset=True)

        # Email changes go through the auth credential + reactivation flow, not here.
        new_email = update_data.pop("email", None)

        # Handle vehicle assignment separately
        vehicle_id = update_data.pop("vehicle_id", None)
        if vehicle_id and self.vehicle_repo:
            # Unassign any current vehicle, then assign new one
            await self.vehicle_repo.unassign_driver_from_all(driver_user_id)
            await self.vehicle_repo.update(vehicle_id, driver_profile_id=driver_user_id)

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

        # If the email changed, update the login credential, deactivate the account,
        # and email a reactivation link to the new address.
        await self._handle_email_change(driver_user_id, detail, new_email, user_fields)

        await self.publisher.publish(
            Exchanges.USERS,
            RoutingKeys.DRIVER_PROFILE_UPDATED,
            {"driver_id": str(driver_user_id)},
        )

        logger.info(f"Admin updated driver: {driver_user_id}")
        return await self.get_driver_detail(driver_user_id)

    async def _handle_email_change(
        self,
        driver_user_id: UUID,
        detail: dict,
        new_email: str | None,
        user_fields: dict,
    ) -> None:
        """Change the driver's login email, deactivate, and queue a reactivation email.

        No-op unless a new, different email was provided.
        """
        if not new_email:
            return
        current_email = (detail.get("email") or "").strip().lower()
        if new_email.strip().lower() == current_email:
            return

        # Updates the auth credential, deactivates the account, returns a token.
        reactivation_token = await self.auth_client.change_email(
            driver_user_id, new_email
        )

        # Keep the user-service copy of the email in sync for display/search.
        await self.repo.update_user(driver_user_id, email=new_email)

        first_name = user_fields.get("first_name") or detail.get("first_name") or ""
        last_name = user_fields.get("last_name") or detail.get("last_name") or ""
        name = f"{first_name} {last_name}".strip() or "there"

        reactivation_link = (
            f"{settings.FRONTEND_URL.rstrip('/')}/reactivate?token={reactivation_token}"
        )

        await self.publisher.publish(
            Exchanges.AUTH,
            RoutingKeys.DRIVER_EMAIL_CHANGED,
            DriverEmailChangedPayload(
                driver_id=driver_user_id,
                email=new_email,
                name=name,
                reactivation_link=reactivation_link,
            ).model_dump(mode="json"),
        )
        logger.info(
            f"Driver email changed; reactivation email queued for {new_email}"
        )

    async def resend_reactivation(self, driver_user_id: UUID) -> str:
        """Re-send the reactivation email to a driver still pending reactivation.

        Only valid while the login is deactivated after an email change; the auth
        service rejects (409 -> ValidationError) if the account is already active.
        Returns the email address the message was sent to.
        """
        detail = await self.repo.get_driver_detail(driver_user_id)
        if not detail:
            raise NotFoundError("Driver not found")

        try:
            reactivation_token = await self.auth_client.resend_reactivation(
                driver_user_id
            )
        except RuntimeError as e:
            raise ValidationError(str(e))

        email = detail.get("email") or ""
        first_name = detail.get("first_name") or ""
        last_name = detail.get("last_name") or ""
        name = f"{first_name} {last_name}".strip() or "there"

        reactivation_link = (
            f"{settings.FRONTEND_URL.rstrip('/')}/reactivate?token={reactivation_token}"
        )

        await self.publisher.publish(
            Exchanges.AUTH,
            RoutingKeys.DRIVER_EMAIL_CHANGED,
            DriverEmailChangedPayload(
                driver_id=driver_user_id,
                email=email,
                name=name,
                reactivation_link=reactivation_link,
            ).model_dump(mode="json"),
        )
        logger.info(
            f"Reactivation email resent to {email} for driver {driver_user_id}"
        )
        return email

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
