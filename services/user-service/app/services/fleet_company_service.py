import asyncio
import logging
from uuid import UUID

from app.clients.payment_service_client import PaymentServiceClient
from app.models.business import Business
from app.models.fleet_document import FleetDocument
from app.repositories.business_repo import BusinessRepository
from app.repositories.driver_repo import DriverRepository
from app.repositories.fleet_company_repo import FleetCompanyRepository
from app.repositories.fleet_document_repo import FleetDocumentRepository
from app.schemas.fleet_company import (
    FleetCompanyDetailResponse,
    FleetCompanyKPIs,
    FleetCompanyResponse,
)
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher

logger = logging.getLogger(__name__)


class FleetCompanyService:
    def __init__(
        self,
        fleet_repo: FleetCompanyRepository,
        business_repo: BusinessRepository,
        driver_repo: DriverRepository,
        doc_repo: FleetDocumentRepository,
        payment_client: PaymentServiceClient,
        publisher: EventPublisher,
    ):
        self.fleet_repo = fleet_repo
        self.business_repo = business_repo
        self.driver_repo = driver_repo
        self.doc_repo = doc_repo
        self.payment_client = payment_client
        self.publisher = publisher

    async def list_fleets(
        self,
        status_filter: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[FleetCompanyResponse], int]:
        rows, total = await self.fleet_repo.list_businesses_with_counts(
            status_filter=status_filter, search=search, offset=offset, limit=limit
        )

        # Enrich with revenue from payment-service (parallel HTTP calls)
        async def _enrich(row: dict) -> FleetCompanyResponse:
            biz = row["business"]
            revenue_data = await self.payment_client.get_fleet_revenue(biz.id)
            revenue = float(revenue_data.get("total_revenue", 0)) if revenue_data else 0.0

            return FleetCompanyResponse(
                id=biz.id,
                name=biz.name,
                contact_person=biz.contact_person,
                email=biz.email,
                phone=biz.phone,
                city=biz.city,
                state=biz.state,
                logo_url=biz.logo_url,
                is_active=biz.is_active,
                vehicle_count=row["vehicle_count"],
                driver_count=row["driver_count"],
                revenue=revenue,
                created_at=biz.created_at,
            )

        enriched = await asyncio.gather(*[_enrich(r) for r in rows])
        return list(enriched), total

    async def get_fleet_kpis(self) -> FleetCompanyKPIs:
        data = await self.fleet_repo.get_fleet_kpis()
        return FleetCompanyKPIs(**data)

    async def add_fleet_partner(
        self, admin_id: UUID, name: str, contact_person: str, email: str, **kwargs
    ) -> Business:
        business = Business(
            name=name,
            contact_person=contact_person,
            email=email,
            city=kwargs.get("city"),
            state=kwargs.get("state"),
            is_active=True,
            onboarded_by=admin_id,
        )
        business = await self.business_repo.create(business)

        await self.publisher.publish(
            exchange_name=Exchanges.USERS,
            routing_key=RoutingKeys.BUSINESS_CREATED,
            payload={
                "business_id": str(business.id),
                "name": business.name,
                "created_by": str(admin_id),
            },
        )

        logger.info(f"Fleet partner added: {business.id}")
        return business

    async def get_fleet_detail(self, business_id: UUID) -> FleetCompanyDetailResponse:
        # Sequential DB queries
        detail = await self.fleet_repo.get_business_detail_with_counts(business_id)
        if not detail:
            raise ValueError(f"Fleet {business_id} not found")

        biz = detail["business"]
        documents = await self.doc_repo.list_by_business(business_id)
        avg_rating = await self.fleet_repo.get_avg_driver_rating(business_id)

        # HTTP call for revenue
        revenue_data = await self.payment_client.get_fleet_revenue(business_id)
        total_revenue = float(revenue_data.get("total_revenue", 0)) if revenue_data else 0.0

        return FleetCompanyDetailResponse(
            id=biz.id,
            name=biz.name,
            contact_person=biz.contact_person,
            email=biz.email,
            phone=biz.phone,
            city=biz.city,
            state=biz.state,
            zip_code=biz.zip_code,
            address=biz.address,
            logo_url=biz.logo_url,
            is_active=biz.is_active,
            vehicle_count=detail["vehicle_count"],
            driver_count=detail["driver_count"],
            total_revenue=total_revenue,
            avg_rating=avg_rating,
            documents=[
                {
                    "id": d.id,
                    "document_type": d.document_type,
                    "file_name": d.file_name,
                    "file_size": d.file_size,
                    "mime_type": d.mime_type,
                    "verification_status": d.verification_status,
                    "created_at": d.created_at,
                }
                for d in documents
            ],
            created_at=biz.created_at,
            updated_at=biz.updated_at,
        )

    async def update_fleet_profile(self, business_id: UUID, **kwargs) -> Business:
        business = await self.business_repo.get_by_id(business_id)
        if not business:
            raise ValueError(f"Fleet {business_id} not found")

        update_data = {k: v for k, v in kwargs.items() if v is not None}
        if update_data:
            await self.business_repo.update(business_id, **update_data)

        await self.publisher.publish(
            exchange_name=Exchanges.USERS,
            routing_key=RoutingKeys.BUSINESS_UPDATED,
            payload={
                "business_id": str(business_id),
                "updated_fields": list(update_data.keys()),
            },
        )

        return await self.business_repo.get_by_id(business_id)

    async def toggle_fleet_status(
        self, business_id: UUID, is_active: bool, admin_id: UUID
    ) -> Business:
        business = await self.business_repo.get_by_id(business_id)
        if not business:
            raise ValueError(f"Fleet {business_id} not found")

        await self.business_repo.update(business_id, is_active=is_active)

        await self.publisher.publish(
            exchange_name=Exchanges.USERS,
            routing_key=RoutingKeys.FLEET_STATUS_CHANGED,
            payload={
                "business_id": str(business_id),
                "is_active": is_active,
                "changed_by": str(admin_id),
            },
        )

        logger.info(f"Fleet {business_id} status changed to {'active' if is_active else 'suspended'}")
        return await self.business_repo.get_by_id(business_id)

    async def upload_document(
        self,
        business_id: UUID,
        document_type: str,
        file_key: str,
        file_name: str,
        file_size: int,
        mime_type: str,
    ) -> FleetDocument:
        business = await self.business_repo.get_by_id(business_id)
        if not business:
            raise ValueError(f"Fleet {business_id} not found")

        doc = FleetDocument(
            business_id=business_id,
            document_type=document_type,
            file_key=file_key,
            file_name=file_name,
            file_size=file_size,
            mime_type=mime_type,
        )
        return await self.doc_repo.create(doc)
