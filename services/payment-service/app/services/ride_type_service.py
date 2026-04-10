import logging
from uuid import UUID

from app.models.service_type_config import ServiceTypeConfig
from app.repositories.service_type_config_repo import ServiceTypeConfigRepository
from app.schemas.ride_type import RideTypeKPIs, RideTypeResponse

logger = logging.getLogger(__name__)


class RideTypeService:
    def __init__(self, config_repo: ServiceTypeConfigRepository):
        self.config_repo = config_repo

    async def get_kpis(self) -> RideTypeKPIs:
        """Get ride type KPI cards."""
        all_types = await self.config_repo.get_all()

        active = sum(1 for t in all_types if t.is_active)
        inactive = len(all_types) - active

        # Calculate average base fare
        base_fares = [
            t.config.get("base_fare", 0)
            for t in all_types
            if isinstance(t.config, dict) and t.config.get("base_fare")
        ]
        avg_base_fare = (
            round(sum(base_fares) / len(base_fares), 2) if base_fares else 0.0
        )

        return RideTypeKPIs(
            total_ride_types=len(all_types),
            active=active,
            inactive=inactive,
            avg_base_fare=avg_base_fare,
        )

    async def list_ride_types(self) -> list[RideTypeResponse]:
        """List all ride types."""
        configs = await self.config_repo.get_all()

        ride_types = []
        for config in configs:
            config_data = config.config if isinstance(config.config, dict) else {}

            ride_types.append(
                RideTypeResponse(
                    id=config.id,
                    service_type=config.service_type,
                    display_name=config.display_name,
                    description=config_data.get("description"),
                    base_fare=float(config_data.get("base_fare", 0)),
                    per_km_rate=float(config_data.get("per_km_rate", 0)),
                    per_min_rate=float(config_data.get("per_min_rate", 0)),
                    min_fare=float(config_data.get("min_fare", 0)),
                    is_active=config.is_active,
                    created_at=config.created_at,
                )
            )

        return ride_types

    async def create_ride_type(
        self,
        service_type: str,
        display_name: str,
        description: str | None,
        base_fare: float,
        per_km_rate: float,
        per_min_rate: float,
        min_fare: float,
        admin_id: UUID,
    ) -> ServiceTypeConfig:
        """Create a new ride type."""
        config = ServiceTypeConfig(
            service_type=service_type,
            display_name=display_name,
            config={
                "description": description,
                "base_fare": base_fare,
                "per_km_rate": per_km_rate,
                "per_min_rate": per_min_rate,
                "min_fare": min_fare,
            },
            created_by=admin_id,
        )
        return await self.config_repo.create(config)

    async def get_ride_type(self, ride_type_id: UUID) -> ServiceTypeConfig:
        """Get ride type by ID."""
        config = await self.config_repo.get_by_id(ride_type_id)
        if not config:
            raise ValueError("Ride type not found")
        return config

    async def update_ride_type(
        self,
        ride_type_id: UUID,
        display_name: str | None = None,
        description: str | None = None,
        base_fare: float | None = None,
        per_km_rate: float | None = None,
        per_min_rate: float | None = None,
        min_fare: float | None = None,
        is_active: bool | None = None,
    ) -> ServiceTypeConfig:
        """Update ride type."""
        config = await self.get_ride_type(ride_type_id)

        if display_name is not None:
            config.display_name = display_name

        # Update config JSON
        if isinstance(config.config, dict):
            if description is not None:
                config.config["description"] = description
            if base_fare is not None:
                config.config["base_fare"] = base_fare
            if per_km_rate is not None:
                config.config["per_km_rate"] = per_km_rate
            if per_min_rate is not None:
                config.config["per_min_rate"] = per_min_rate
            if min_fare is not None:
                config.config["min_fare"] = min_fare

        if is_active is not None:
            config.is_active = is_active

        return await self.config_repo.update(config)

    async def toggle_ride_type(
        self, ride_type_id: UUID, is_active: bool
    ) -> ServiceTypeConfig:
        """Toggle ride type active status."""
        return await self.update_ride_type(ride_type_id, is_active=is_active)

    async def delete_ride_type(self, ride_type_id: UUID) -> None:
        """Delete a ride type."""
        config = await self.get_ride_type(ride_type_id)
        await self.config_repo.delete(config.id)
