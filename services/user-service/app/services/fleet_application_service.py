import logging
from datetime import datetime, timezone
from uuid import UUID

from app.models.fleet import Fleet
from app.models.fleet_application import FleetApplication
from app.models.fleet_document import FleetDocument
from app.repositories.fleet_repo import FleetRepository
from app.repositories.fleet_application_repo import FleetApplicationRepository
from app.repositories.fleet_document_repo import FleetDocumentRepository
from app.schemas.fleet_application import FleetApplicationKPIs
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.enums import FleetApplicationStatus

logger = logging.getLogger(__name__)


class FleetApplicationService:
    def __init__(
        self,
        app_repo: FleetApplicationRepository,
        doc_repo: FleetDocumentRepository,
        fleet_repo: FleetRepository,
        publisher: EventPublisher,
    ):
        self.app_repo = app_repo
        self.doc_repo = doc_repo
        self.fleet_repo = fleet_repo
        self.publisher = publisher

    async def create_application(self, admin_id: UUID, **kwargs) -> FleetApplication:
        application = FleetApplication(**kwargs)
        application = await self.app_repo.create(application)

        await self.publisher.publish(
            exchange_name=Exchanges.USERS,
            routing_key=RoutingKeys.FLEET_APPLICATION_CREATED,
            payload={
                "application_id": str(application.id),
                "company_name": application.company_name,
                "email": application.email,
                "created_by": str(admin_id),
            },
        )

        logger.info(f"Fleet application created: {application.id}")
        return application

    async def create_public_application(
        self,
        publish_created_event: bool = True,
        **kwargs,
    ) -> FleetApplication:
        """Create a fleet application from a public (unauthenticated) submission."""
        application = FleetApplication(**kwargs)
        application = await self.app_repo.create(application)

        if publish_created_event:
            await self.publisher.publish(
                exchange_name=Exchanges.USERS,
                routing_key=RoutingKeys.FLEET_APPLICATION_CREATED,
                payload={
                    "application_id": str(application.id),
                    "company_name": application.company_name,
                    "email": application.email,
                    "created_by": "public",
                },
            )

        logger.info(f"Public fleet application created: {application.id}")
        return application

    async def list_applications(
        self,
        status_filter: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[FleetApplication], int]:
        return await self.app_repo.list_all(
            status_filter=status_filter,
            offset=offset,
            limit=limit,
        )

    async def get_application(self, app_id: UUID) -> FleetApplication:
        application = await self.app_repo.get_by_id(app_id)
        if not application:
            raise ValueError(f"Application {app_id} not found")
        return application

    async def get_kpis(self) -> FleetApplicationKPIs:
        data = await self.app_repo.get_kpis()
        return FleetApplicationKPIs(**data)

    async def approve_application(
        self, app_id: UUID, admin_id: UUID, notes: str | None = None
    ) -> FleetApplication:
        application = await self.get_application(app_id)

        if application.status not in (
            FleetApplicationStatus.PENDING,
            FleetApplicationStatus.MORE_INFO_REQUESTED,
        ):
            raise ValueError(
                f"Cannot approve application with status '{application.status}'"
            )

        # Create Fleet entity from application data
        fleet = Fleet(
            name=application.company_name,
            contact_person=application.contact_person,
            email=application.email,
            phone=application.phone,
            city=application.city,
            state=application.province,
            is_active=True,
            onboarded_by=admin_id,
        )
        fleet = await self.fleet_repo.create(fleet)

        # Update application
        now = datetime.now(timezone.utc)
        await self.app_repo.update(
            app_id,
            status=FleetApplicationStatus.APPROVED,
            business_id=fleet.id,
            reviewed_by=admin_id,
            reviewed_at=now,
        )

        # Transfer documents from application to fleet
        for doc in application.documents:
            await self.doc_repo.update(doc.id, business_id=fleet.id)

        await self.publisher.publish(
            exchange_name=Exchanges.USERS,
            routing_key=RoutingKeys.FLEET_APPLICATION_APPROVED,
            payload={
                "application_id": str(app_id),
                "fleet_id": str(fleet.id),
                "company_name": application.company_name,
                "email": application.email,
                "approved_by": str(admin_id),
            },
        )

        logger.info(f"Fleet application {app_id} approved, fleet {fleet.id} created")
        return await self.get_application(app_id)

    async def reject_application(
        self, app_id: UUID, admin_id: UUID, reason: str
    ) -> FleetApplication:
        application = await self.get_application(app_id)

        if application.status not in (
            FleetApplicationStatus.PENDING,
            FleetApplicationStatus.MORE_INFO_REQUESTED,
        ):
            raise ValueError(
                f"Cannot reject application with status '{application.status}'"
            )

        now = datetime.now(timezone.utc)
        await self.app_repo.update(
            app_id,
            status=FleetApplicationStatus.REJECTED,
            rejection_reason=reason,
            reviewed_by=admin_id,
            reviewed_at=now,
        )

        await self.publisher.publish(
            exchange_name=Exchanges.USERS,
            routing_key=RoutingKeys.FLEET_APPLICATION_REJECTED,
            payload={
                "application_id": str(app_id),
                "company_name": application.company_name,
                "email": application.email,
                "rejected_by": str(admin_id),
                "reason": reason,
            },
        )

        logger.info(f"Fleet application {app_id} rejected")
        return await self.get_application(app_id)

    async def request_info(
        self, app_id: UUID, admin_id: UUID, message: str
    ) -> FleetApplication:
        application = await self.get_application(app_id)

        if application.status not in (
            FleetApplicationStatus.PENDING,
            FleetApplicationStatus.MORE_INFO_REQUESTED,
        ):
            raise ValueError(
                f"Cannot request info for application with status '{application.status}'"
            )

        await self.app_repo.update(
            app_id,
            status=FleetApplicationStatus.MORE_INFO_REQUESTED,
            info_request_message=message,
            reviewed_by=admin_id,
        )

        await self.publisher.publish(
            exchange_name=Exchanges.USERS,
            routing_key=RoutingKeys.FLEET_APPLICATION_INFO_REQUESTED,
            payload={
                "application_id": str(app_id),
                "company_name": application.company_name,
                "email": application.email,
                "message": message,
                "requested_by": str(admin_id),
            },
        )

        logger.info(f"Fleet application {app_id} - more info requested")
        return await self.get_application(app_id)

    async def delete_application(self, app_id: UUID, admin_id: UUID) -> list[str]:
        """Delete a fleet application and its owned documents.

        Documents that were transferred to a fleet on approval (``business_id``
        set) are detached from the application rather than deleted, so the
        fleet's records stay intact. Returns the S3 file keys of the documents
        that were actually deleted, so the caller can clean up object storage.
        """
        application = await self.get_application(app_id)

        deleted_file_keys: list[str] = []
        for doc in list(application.documents):
            if doc.business_id is not None:
                await self.doc_repo.update(doc.id, application_id=None)
            else:
                deleted_file_keys.append(doc.file_key)
                await self.doc_repo.delete(doc.id)

        await self.app_repo.delete(app_id)

        logger.info(f"Fleet application {app_id} deleted by {admin_id}")
        return deleted_file_keys

    async def upload_document(
        self,
        app_id: UUID,
        document_type: str,
        file_key: str,
        file_name: str,
        file_size: int,
        mime_type: str,
    ) -> FleetDocument:
        # Verify application exists
        await self.get_application(app_id)

        doc = FleetDocument(
            application_id=app_id,
            document_type=document_type,
            file_key=file_key,
            file_name=file_name,
            file_size=file_size,
            mime_type=mime_type,
        )
        return await self.doc_repo.create(doc)
