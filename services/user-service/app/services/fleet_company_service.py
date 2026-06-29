import asyncio
import logging
from uuid import UUID

from app.clients.payment_service_client import PaymentServiceClient
from app.models.fleet import Fleet
from app.models.fleet_document import FleetDocument
from app.repositories.fleet_repo import FleetRepository
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
        fleet_company_repo: FleetCompanyRepository,
        fleet_repo: FleetRepository,
        driver_repo: DriverRepository,
        doc_repo: FleetDocumentRepository,
        payment_client: PaymentServiceClient,
        publisher: EventPublisher,
    ):
        self.fleet_company_repo = fleet_company_repo
        self.fleet_repo = fleet_repo
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
        rows, total = await self.fleet_company_repo.list_fleets_with_counts(
            status_filter=status_filter, search=search, offset=offset, limit=limit
        )

        # Enrich with revenue from payment-service (parallel HTTP calls)
        async def _enrich(row: dict) -> FleetCompanyResponse:
            fleet = row["fleet"]
            revenue_data = await self.payment_client.get_fleet_revenue(fleet.id)
            revenue = float(revenue_data.get("total_revenue", 0)) if revenue_data else 0.0

            return FleetCompanyResponse(
                id=fleet.id,
                name=fleet.name,
                contact_person=fleet.contact_person,
                email=fleet.email,
                phone=fleet.phone,
                city=fleet.city,
                state=fleet.state,
                logo_url=fleet.logo_url,
                is_active=fleet.is_active,
                vehicle_count=row["vehicle_count"],
                driver_count=row["driver_count"],
                revenue=revenue,
                created_at=fleet.created_at,
            )

        enriched = await asyncio.gather(*[_enrich(r) for r in rows])
        return list(enriched), total

    async def get_fleet_kpis(self) -> FleetCompanyKPIs:
        data = await self.fleet_company_repo.get_fleet_kpis()
        return FleetCompanyKPIs(**data)

    async def add_fleet_partner(
        self, admin_id: UUID, name: str, contact_person: str, email: str, **kwargs
    ) -> Fleet:
        fleet = Fleet(
            name=name,
            contact_person=contact_person,
            email=email,
            city=kwargs.get("city"),
            state=kwargs.get("state"),
            is_active=True,
            onboarded_by=admin_id,
        )
        fleet = await self.fleet_repo.create(fleet)

        await self.publisher.publish(
            exchange_name=Exchanges.USERS,
            routing_key=RoutingKeys.FLEET_CREATED,
            payload={
                "fleet_id": str(fleet.id),
                "name": fleet.name,
                "created_by": str(admin_id),
            },
        )

        logger.info(f"Fleet partner added: {fleet.id}")
        return fleet

    async def get_fleet_detail(self, fleet_id: UUID) -> FleetCompanyDetailResponse:
        # Sequential DB queries
        detail = await self.fleet_company_repo.get_fleet_detail_with_counts(fleet_id)
        if not detail:
            raise ValueError(f"Fleet {fleet_id} not found")

        fleet = detail["fleet"]
        documents = await self.doc_repo.list_by_fleet(fleet_id)
        avg_rating = await self.fleet_company_repo.get_avg_driver_rating(fleet_id)

        # HTTP call for revenue
        revenue_data = await self.payment_client.get_fleet_revenue(fleet_id)
        total_revenue = float(revenue_data.get("total_revenue", 0)) if revenue_data else 0.0

        return FleetCompanyDetailResponse(
            id=fleet.id,
            name=fleet.name,
            contact_person=fleet.contact_person,
            email=fleet.email,
            phone=fleet.phone,
            city=fleet.city,
            state=fleet.state,
            zip_code=fleet.zip_code,
            address=fleet.address,
            logo_url=fleet.logo_url,
            is_active=fleet.is_active,
            vehicle_count=detail["vehicle_count"],
            driver_count=detail["driver_count"],
            total_revenue=total_revenue,
            avg_rating=avg_rating,
            documents=[
                {
                    "id": d.id,
                    "document_type": d.document_type,
                    "file_key": d.file_key,
                    "file_name": d.file_name,
                    "file_size": d.file_size,
                    "mime_type": d.mime_type,
                    "verification_status": d.verification_status,
                    "created_at": d.created_at,
                }
                for d in documents
            ],
            created_at=fleet.created_at,
            updated_at=fleet.updated_at,
        )

    async def get_all_fleet_details(self) -> list[FleetCompanyDetailResponse]:
        rows = await self.fleet_company_repo.get_all_fleet_details_with_counts()

        async def _build_detail(row: dict) -> FleetCompanyDetailResponse:
            fleet = row["fleet"]
            # Sequential DB queries per fleet
            documents = await self.doc_repo.list_by_fleet(fleet.id)
            avg_rating = await self.fleet_company_repo.get_avg_driver_rating(fleet.id)

            # HTTP call for revenue
            revenue_data = await self.payment_client.get_fleet_revenue(fleet.id)
            total_revenue = float(revenue_data.get("total_revenue", 0)) if revenue_data else 0.0

            return FleetCompanyDetailResponse(
                id=fleet.id,
                name=fleet.name,
                contact_person=fleet.contact_person,
                email=fleet.email,
                phone=fleet.phone,
                city=fleet.city,
                state=fleet.state,
                zip_code=fleet.zip_code,
                address=fleet.address,
                logo_url=fleet.logo_url,
                is_active=fleet.is_active,
                vehicle_count=row["vehicle_count"],
                driver_count=row["driver_count"],
                total_revenue=total_revenue,
                avg_rating=avg_rating,
                documents=[
                    {
                        "id": d.id,
                        "document_type": d.document_type,
                        "file_key": d.file_key,
                        "file_name": d.file_name,
                        "file_size": d.file_size,
                        "mime_type": d.mime_type,
                        "verification_status": d.verification_status,
                        "created_at": d.created_at,
                    }
                    for d in documents
                ],
                created_at=fleet.created_at,
                updated_at=fleet.updated_at,
            )

        # DB queries must be sequential (same async session), but HTTP calls can be parallel
        # Build details sequentially since docs + rating share the session
        results = []
        for row in rows:
            detail = await _build_detail(row)
            results.append(detail)
        return results

    async def update_fleet_profile(self, fleet_id: UUID, **kwargs) -> Fleet:
        fleet = await self.fleet_repo.get_by_id(fleet_id)
        if not fleet:
            raise ValueError(f"Fleet {fleet_id} not found")

        update_data = {k: v for k, v in kwargs.items() if v is not None}
        if update_data:
            await self.fleet_repo.update(fleet_id, **update_data)

        await self.publisher.publish(
            exchange_name=Exchanges.USERS,
            routing_key=RoutingKeys.FLEET_UPDATED,
            payload={
                "fleet_id": str(fleet_id),
                "updated_fields": list(update_data.keys()),
            },
        )

        return await self.fleet_repo.get_by_id(fleet_id)

    async def toggle_fleet_status(
        self, fleet_id: UUID, is_active: bool, admin_id: UUID
    ) -> Fleet:
        fleet = await self.fleet_repo.get_by_id(fleet_id)
        if not fleet:
            raise ValueError(f"Fleet {fleet_id} not found")

        await self.fleet_repo.update(fleet_id, is_active=is_active)

        await self.publisher.publish(
            exchange_name=Exchanges.USERS,
            routing_key=RoutingKeys.FLEET_STATUS_CHANGED,
            payload={
                "fleet_id": str(fleet_id),
                "is_active": is_active,
                "changed_by": str(admin_id),
            },
        )

        logger.info(f"Fleet {fleet_id} status changed to {'active' if is_active else 'suspended'}")
        return await self.fleet_repo.get_by_id(fleet_id)

    async def upload_document(
        self,
        fleet_id: UUID,
        document_type: str,
        file_key: str,
        file_name: str,
        file_size: int,
        mime_type: str,
    ) -> FleetDocument:
        fleet = await self.fleet_repo.get_by_id(fleet_id)
        if not fleet:
            raise ValueError(f"Fleet {fleet_id} not found")

        doc = FleetDocument(
            business_id=fleet_id,
            document_type=document_type,
            file_key=file_key,
            file_name=file_name,
            file_size=file_size,
            mime_type=mime_type,
        )
        return await self.doc_repo.create(doc)
