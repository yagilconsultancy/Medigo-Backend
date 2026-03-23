import logging
from uuid import UUID

from app.models.vehicle import Vehicle
from app.models.vehicle_maintenance_log import VehicleMaintenanceLog
from app.repositories.business_repo import BusinessRepository
from app.repositories.driver_repo import DriverRepository
from app.repositories.maintenance_log_repo import VehicleMaintenanceLogRepository
from app.repositories.user_repo import UserRepository
from app.repositories.vehicle_repo import VehicleRepository
from app.schemas.fleet_vehicle import (
    MaintenanceLogResponse,
    VehicleDetailResponse,
    VehicleKPIs,
    VehicleResponse,
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
        business_repo: BusinessRepository,
        driver_repo: DriverRepository,
        user_repo: UserRepository,
        publisher: EventPublisher,
    ):
        self.vehicle_repo = vehicle_repo
        self.maintenance_repo = maintenance_repo
        self.business_repo = business_repo
        self.driver_repo = driver_repo
        self.user_repo = user_repo
        self.publisher = publisher

    async def create_vehicle(self, admin_id: UUID, **kwargs) -> VehicleResponse:
        business_id = kwargs.get("business_id")
        business = await self.business_repo.get_by_id(business_id)
        if not business:
            raise ValueError(f"Business {business_id} not found")

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
        self, vehicle_id: UUID, scheduled_date, admin_id: UUID, notes: str | None = None
    ) -> VehicleMaintenanceLog:
        vehicle = await self.vehicle_repo.get_by_id(vehicle_id)
        if not vehicle:
            raise ValueError(f"Vehicle {vehicle_id} not found")

        log = VehicleMaintenanceLog(
            vehicle_id=vehicle_id,
            scheduled_date=scheduled_date,
            notes=notes,
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

    async def _to_response(self, vehicle: Vehicle) -> VehicleResponse:
        """Enrich vehicle with business name and driver name."""
        business_name = None
        driver_name = None

        business = await self.business_repo.get_by_id(vehicle.business_id)
        if business:
            business_name = business.name

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
            created_at=vehicle.created_at,
            business_name=business_name,
            driver_name=driver_name,
        )
