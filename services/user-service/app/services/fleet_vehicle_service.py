import logging
from datetime import date
from uuid import UUID

from app.models.vehicle import Vehicle
from app.models.vehicle_document import VehicleDocument
from app.models.vehicle_maintenance_log import VehicleMaintenanceLog
from app.repositories.fleet_repo import FleetRepository
from app.repositories.driver_repo import DriverRepository
from app.repositories.maintenance_log_repo import VehicleMaintenanceLogRepository
from app.repositories.user_repo import UserRepository
from app.repositories.vehicle_category_config_repo import VehicleCategoryConfigRepository
from app.repositories.vehicle_document_repo import VehicleDocumentRepository
from app.repositories.vehicle_repo import VehicleRepository
from app.schemas.fleet_vehicle import (
    MaintenanceLogResponse,
    VehicleDetailResponse,
    VehicleKPIs,
    VehicleProfileResponse,
    VehicleResponse,
)
from app.schemas.vehicle_category import (
    VehicleCategoryConfigResponse,
    VehicleCategoryConfigUpdate,
    VehicleCategoryFleetComposition,
)
from app.schemas.vehicle_document import (
    VehicleDocumentKPIs,
    VehicleDocumentOverview,
    VehicleDocumentOverviewItem,
    VehicleDocumentMatrixItem,
    VehicleDocumentResponse,
    VehicleDocumentUploadResponse,
)
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.enums import VehicleStatus

logger = logging.getLogger(__name__)


class FleetVehicleService:
    def __init__(
        self,
        vehicle_repo: VehicleRepository,
        maintenance_repo: VehicleMaintenanceLogRepository,
        fleet_repo: FleetRepository,
        driver_repo: DriverRepository,
        user_repo: UserRepository,
        publisher: EventPublisher,
        vehicle_doc_repo: VehicleDocumentRepository | None = None,
        category_config_repo: VehicleCategoryConfigRepository | None = None,
    ):
        self.vehicle_repo = vehicle_repo
        self.maintenance_repo = maintenance_repo
        self.fleet_repo = fleet_repo
        self.driver_repo = driver_repo
        self.user_repo = user_repo
        self.publisher = publisher
        self.vehicle_doc_repo = vehicle_doc_repo
        self.category_config_repo = category_config_repo

    async def create_vehicle(self, admin_id: UUID, **kwargs) -> VehicleResponse:
        business_id = kwargs.get("business_id")
        fleet = await self.fleet_repo.get_by_id(business_id)
        if not fleet:
            raise ValueError(f"Fleet {business_id} not found")

        # Check unique plate
        existing = await self.vehicle_repo.get_by_plate(kwargs["plate_number"])
        if existing:
            raise ValueError(f"Vehicle with plate {kwargs['plate_number']} already exists")

        # Check unique VIN if provided
        vin = kwargs.get("vin")
        if vin:
            existing_vin = await self.vehicle_repo.get_by_vin(vin)
            if existing_vin:
                raise ValueError(f"Vehicle with VIN {vin} already exists")

        vehicle = Vehicle(**kwargs)
        vehicle = await self.vehicle_repo.create(vehicle)

        await self.publisher.publish(
            exchange_name=Exchanges.USERS,
            routing_key=RoutingKeys.FLEET_VEHICLE_CREATED,
            payload={
                "vehicle_id": str(vehicle.id),
                "business_id": str(vehicle.business_id),
                "plate_number": vehicle.plate_number,
                "category": vehicle.category,
            },
        )

        logger.info(f"Vehicle created: {vehicle.id}")
        return await self._to_response(vehicle)

    async def list_vehicles(
        self,
        business_id: UUID | None = None,
        status_filter: str | None = None,
        category_filter: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[VehicleResponse], int]:
        vehicles, total = await self.vehicle_repo.list_all(
            business_id=business_id,
            status_filter=status_filter,
            category_filter=category_filter,
            search=search,
            offset=offset,
            limit=limit,
        )
        responses = []
        for v in vehicles:
            responses.append(await self._to_response(v))
        return responses, total

    async def get_vehicle(self, vehicle_id: UUID) -> VehicleDetailResponse:
        vehicle = await self.vehicle_repo.get_by_id(vehicle_id)
        if not vehicle:
            raise ValueError(f"Vehicle {vehicle_id} not found")

        base = await self._to_response(vehicle)
        return VehicleDetailResponse(
            **base.model_dump(),
            maintenance_logs=[
                MaintenanceLogResponse.model_validate(log)
                for log in (vehicle.maintenance_logs or [])
            ],
            documents=[
                VehicleDocumentResponse.model_validate(doc)
                for doc in (vehicle.documents or [])
            ],
        )

    async def update_vehicle(self, vehicle_id: UUID, **kwargs) -> VehicleResponse:
        vehicle = await self.vehicle_repo.get_by_id(vehicle_id)
        if not vehicle:
            raise ValueError(f"Vehicle {vehicle_id} not found")

        update_data = {k: v for k, v in kwargs.items() if v is not None}
        if update_data:
            await self.vehicle_repo.update(vehicle_id, **update_data)

        vehicle = await self.vehicle_repo.get_by_id(vehicle_id)
        return await self._to_response(vehicle)

    async def change_status(
        self, vehicle_id: UUID, new_status: str, admin_id: UUID
    ) -> VehicleResponse:
        vehicle = await self.vehicle_repo.get_by_id(vehicle_id)
        if not vehicle:
            raise ValueError(f"Vehicle {vehicle_id} not found")

        valid_statuses = [s.value for s in VehicleStatus]
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status: {new_status}")

        old_status = vehicle.status
        await self.vehicle_repo.update(vehicle_id, status=new_status)

        await self.publisher.publish(
            exchange_name=Exchanges.USERS,
            routing_key=RoutingKeys.FLEET_VEHICLE_STATUS_CHANGED,
            payload={
                "vehicle_id": str(vehicle_id),
                "business_id": str(vehicle.business_id),
                "old_status": old_status,
                "new_status": new_status,
            },
        )

        logger.info(f"Vehicle {vehicle_id} status: {old_status} -> {new_status}")
        vehicle = await self.vehicle_repo.get_by_id(vehicle_id)
        return await self._to_response(vehicle)

    async def assign_driver(
        self, vehicle_id: UUID, driver_id: UUID
    ) -> VehicleResponse:
        vehicle = await self.vehicle_repo.get_by_id(vehicle_id)
        if not vehicle:
            raise ValueError(f"Vehicle {vehicle_id} not found")

        driver = await self.driver_repo.get_by_user_id(driver_id)
        if not driver:
            raise ValueError(f"Driver {driver_id} not found")

        if driver.business_id != vehicle.business_id:
            raise ValueError("Driver does not belong to the same fleet as this vehicle")

        # Unassign driver from any other vehicle first
        await self.vehicle_repo.unassign_driver_from_all(driver_id)

        # Assign to this vehicle
        await self.vehicle_repo.update(vehicle_id, driver_profile_id=driver_id)

        vehicle = await self.vehicle_repo.get_by_id(vehicle_id)
        return await self._to_response(vehicle)

    async def unassign_driver(self, vehicle_id: UUID) -> VehicleResponse:
        vehicle = await self.vehicle_repo.get_by_id(vehicle_id)
        if not vehicle:
            raise ValueError(f"Vehicle {vehicle_id} not found")

        await self.vehicle_repo.update(vehicle_id, driver_profile_id=None)

        vehicle = await self.vehicle_repo.get_by_id(vehicle_id)
        return await self._to_response(vehicle)

    async def schedule_maintenance(
        self,
        vehicle_id: UUID,
        scheduled_date,
        admin_id: UUID,
        notes: str | None = None,
        service_type: str | None = None,
        technician_notes: str | None = None,
    ) -> VehicleMaintenanceLog:
        vehicle = await self.vehicle_repo.get_by_id(vehicle_id)
        if not vehicle:
            raise ValueError(f"Vehicle {vehicle_id} not found")

        log = VehicleMaintenanceLog(
            vehicle_id=vehicle_id,
            scheduled_date=scheduled_date,
            service_type=service_type,
            notes=notes,
            technician_notes=technician_notes,
            created_by=admin_id,
        )
        log = await self.maintenance_repo.create(log)

        await self.publisher.publish(
            exchange_name=Exchanges.USERS,
            routing_key=RoutingKeys.FLEET_VEHICLE_MAINTENANCE_SCHEDULED,
            payload={
                "vehicle_id": str(vehicle_id),
                "business_id": str(vehicle.business_id),
                "scheduled_date": str(scheduled_date),
                "service_type": service_type,
                "notes": notes,
            },
        )

        logger.info(f"Maintenance scheduled for vehicle {vehicle_id}")
        return log

    async def get_kpis(self, business_id: UUID | None = None) -> VehicleKPIs:
        data = await self.vehicle_repo.get_kpis(business_id)
        return VehicleKPIs(**data)

    async def delete_vehicle(self, vehicle_id: UUID) -> None:
        vehicle = await self.vehicle_repo.get_by_id(vehicle_id)
        if not vehicle:
            raise ValueError(f"Vehicle {vehicle_id} not found")
        await self.vehicle_repo.soft_delete(vehicle_id)
        logger.info(f"Vehicle {vehicle_id} soft deleted")

    # --- Vehicle Documents ---

    async def upload_vehicle_document(
        self,
        vehicle_id: UUID,
        document_type: str,
        file_key: str,
        file_name: str,
        file_size: int,
        mime_type: str,
        admin_id: UUID,
        expires_at: date | None = None,
        notes: str | None = None,
    ) -> VehicleDocumentUploadResponse:
        vehicle = await self.vehicle_repo.get_by_id(vehicle_id)
        if not vehicle:
            raise ValueError(f"Vehicle {vehicle_id} not found")

        doc = VehicleDocument(
            vehicle_id=vehicle_id,
            document_type=document_type,
            file_key=file_key,
            file_name=file_name,
            file_size=file_size,
            mime_type=mime_type,
            expires_at=expires_at,
            status="valid",
            uploaded_by=admin_id,
            notes=notes,
        )
        doc = await self.vehicle_doc_repo.create(doc)

        await self.publisher.publish(
            exchange_name=Exchanges.USERS,
            routing_key=RoutingKeys.VEHICLE_DOCUMENT_UPLOADED,
            payload={
                "vehicle_id": str(vehicle_id),
                "document_type": document_type,
                "document_id": str(doc.id),
            },
        )

        logger.info(f"Document uploaded for vehicle {vehicle_id}: {document_type}")
        return VehicleDocumentUploadResponse.model_validate(doc)

    async def replace_vehicle_document(
        self,
        vehicle_id: UUID,
        doc_id: UUID,
        file_key: str,
        file_name: str,
        file_size: int,
        mime_type: str,
        admin_id: UUID,
        expires_at: date | None = None,
        notes: str | None = None,
    ) -> VehicleDocumentUploadResponse:
        vehicle = await self.vehicle_repo.get_by_id(vehicle_id)
        if not vehicle:
            raise ValueError(f"Vehicle {vehicle_id} not found")

        old_doc = await self.vehicle_doc_repo.get_by_id(doc_id)
        if not old_doc or old_doc.vehicle_id != vehicle_id:
            raise ValueError(f"Document {doc_id} not found for vehicle {vehicle_id}")

        new_doc = VehicleDocument(
            vehicle_id=vehicle_id,
            document_type=old_doc.document_type,
            file_key=file_key,
            file_name=file_name,
            file_size=file_size,
            mime_type=mime_type,
            expires_at=expires_at,
            status="valid",
            uploaded_by=admin_id,
            notes=notes,
        )
        new_doc = await self.vehicle_doc_repo.create(new_doc)

        await self.publisher.publish(
            exchange_name=Exchanges.USERS,
            routing_key=RoutingKeys.VEHICLE_DOCUMENT_REPLACED,
            payload={
                "vehicle_id": str(vehicle_id),
                "old_document_id": str(doc_id),
                "new_document_id": str(new_doc.id),
                "document_type": old_doc.document_type,
            },
        )

        logger.info(f"Document replaced for vehicle {vehicle_id}: {old_doc.document_type}")
        return VehicleDocumentUploadResponse.model_validate(new_doc)

    async def get_vehicle_documents(self, vehicle_id: UUID) -> list[VehicleDocumentResponse]:
        vehicle = await self.vehicle_repo.get_by_id(vehicle_id)
        if not vehicle:
            raise ValueError(f"Vehicle {vehicle_id} not found")

        docs = await self.vehicle_doc_repo.list_by_vehicle(vehicle_id)
        return [VehicleDocumentResponse.model_validate(d) for d in docs]

    async def get_vehicle_document_overview(
        self,
        search: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> VehicleDocumentOverview:
        offset = (page - 1) * limit
        kpis_data = await self.vehicle_doc_repo.get_document_kpis()
        kpis = VehicleDocumentKPIs(**kpis_data)

        vehicles_data, total = await self.vehicle_doc_repo.get_document_overview(
            search=search, offset=offset, limit=limit
        )

        vehicles = [
            VehicleDocumentOverviewItem(
                vehicle_id=v["vehicle_id"],
                vehicle_name=v["vehicle_name"],
                make=v["make"],
                model=v["model"],
                plate_number=v["plate_number"],
                fleet_name=v["fleet_name"],
                documents=[VehicleDocumentMatrixItem(**d) for d in v["documents"]],
            )
            for v in vehicles_data
        ]

        return VehicleDocumentOverview(
            kpis=kpis,
            vehicles=vehicles,
            total=total,
            page=page,
            limit=limit,
            total_pages=(total + limit - 1) // limit if total > 0 else 0,
        )

    # --- Vehicle Categories ---

    async def list_category_configs(self) -> list[VehicleCategoryConfigResponse]:
        configs = await self.category_config_repo.list_all()
        return [VehicleCategoryConfigResponse.model_validate(c) for c in configs]

    async def update_category_config(
        self, category: str, updates: VehicleCategoryConfigUpdate
    ) -> VehicleCategoryConfigResponse:
        config = await self.category_config_repo.get_by_category(category)
        if not config:
            raise ValueError(f"Category config '{category}' not found")

        update_data = updates.model_dump(exclude_unset=True)
        if update_data:
            await self.category_config_repo.update(config.id, **update_data)

        config = await self.category_config_repo.get_by_category(category)

        await self.publisher.publish(
            exchange_name=Exchanges.USERS,
            routing_key=RoutingKeys.VEHICLE_CATEGORY_UPDATED,
            payload={"category": category},
        )

        logger.info(f"Vehicle category config updated: {category}")
        return VehicleCategoryConfigResponse.model_validate(config)

    async def get_fleet_composition(self) -> VehicleCategoryFleetComposition:
        data = await self.category_config_repo.get_fleet_composition()
        return VehicleCategoryFleetComposition(**data)

    # --- Vehicle Profiles ---

    async def get_vehicle_profiles(
        self,
        search: str | None = None,
        category: str | None = None,
        fleet_id: UUID | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[VehicleProfileResponse], int]:
        offset = (page - 1) * limit
        vehicles, total = await self.vehicle_repo.list_all(
            business_id=fleet_id,
            category_filter=category,
            search=search,
            offset=offset,
            limit=limit,
        )

        profiles = []
        for v in vehicles:
            base = await self._to_response(v)
            profiles.append(
                VehicleProfileResponse(
                    **base.model_dump(),
                    maintenance_logs=[
                        MaintenanceLogResponse.model_validate(log)
                        for log in (v.maintenance_logs or [])
                    ],
                    documents=[
                        VehicleDocumentResponse.model_validate(doc)
                        for doc in (v.documents or [])
                    ],
                )
            )
        return profiles, total

    async def _to_response(self, vehicle: Vehicle) -> VehicleResponse:
        """Enrich vehicle with fleet name and driver name."""
        fleet_name = None
        driver_name = None

        fleet = await self.fleet_repo.get_by_id(vehicle.business_id)
        if fleet:
            fleet_name = fleet.name

        if vehicle.driver_profile_id:
            user = await self.user_repo.get_by_id(vehicle.driver_profile_id)
            if user:
                driver_name = f"{user.first_name} {user.last_name}"

        return VehicleResponse(
            id=vehicle.id,
            business_id=vehicle.business_id,
            driver_profile_id=vehicle.driver_profile_id,
            vehicle_name=vehicle.vehicle_name,
            make=vehicle.make,
            model=vehicle.model,
            year=vehicle.year,
            plate_number=vehicle.plate_number,
            color=vehicle.color,
            vin=vehicle.vin,
            category=vehicle.category,
            status=vehicle.status,
            photo_url=vehicle.photo_url,
            mileage=vehicle.mileage,
            insurance_expiry=vehicle.insurance_expiry,
            registration_expiry=vehicle.registration_expiry,
            passenger_capacity=vehicle.passenger_capacity,
            special_equipment=vehicle.special_equipment,
            insurance_provider=vehicle.insurance_provider,
            registration_authority=vehicle.registration_authority,
            last_inspection_date=vehicle.last_inspection_date,
            internal_notes=vehicle.internal_notes,
            created_at=vehicle.created_at,
            fleet_name=fleet_name,
            driver_name=driver_name,
        )
