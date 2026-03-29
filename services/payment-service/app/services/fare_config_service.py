import logging
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.commission_config_repo import CommissionConfigRepository
from app.repositories.pricing_change_log_repo import PricingChangeLogRepository
from app.repositories.service_type_config_repo import ServiceTypeConfigRepository

logger = logging.getLogger(__name__)


class FareConfigService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.config_repo = ServiceTypeConfigRepository(session)
        self.log_repo = PricingChangeLogRepository(session)
        self.commission_repo = CommissionConfigRepository(session)

    async def get_service_types(self) -> list[dict]:
        configs = await self.config_repo.get_all()
        return [
            {
                "service_type": c.service_type,
                "display_name": c.display_name,
                "is_active": c.is_active,
                "sort_order": c.sort_order,
            }
            for c in configs
        ]

    async def get_config(self, service_type: str) -> dict | None:
        obj = await self.config_repo.get_by_service_type(service_type)
        if not obj:
            return None
        return {
            "id": obj.id,
            "service_type": obj.service_type,
            "display_name": obj.display_name,
            "config": obj.config,
            "is_active": obj.is_active,
            "sort_order": obj.sort_order,
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
        }

    async def update_config(
        self, service_type: str, config: dict, admin_id: uuid.UUID, admin_name: str
    ) -> dict | None:
        obj = await self.config_repo.get_by_service_type(service_type)
        if not obj:
            return None

        old_config = obj.config
        updated = await self.config_repo.update_config(service_type, config)

        await self.log_repo.create({
            "admin_id": admin_id,
            "admin_name": admin_name,
            "category": "fare",
            "change_description": f"Updated {service_type} fare configuration",
            "before_value": str(old_config.get("rate_components", {}))[:200] if old_config else None,
            "after_value": str(config.get("rate_components", {}))[:200],
        })

        return {
            "id": updated.id,
            "service_type": updated.service_type,
            "display_name": updated.display_name,
            "config": updated.config,
            "is_active": updated.is_active,
            "sort_order": updated.sort_order,
            "created_at": updated.created_at,
            "updated_at": updated.updated_at,
        }

    async def get_routes(self, service_type: str) -> dict | None:
        obj = await self.config_repo.get_by_service_type(service_type)
        if not obj:
            return None

        config_data = obj.config or {}
        route_pricing = config_data.get("route_pricing", {})
        routes = []
        for route_key, route_data in route_pricing.items():
            route_label = route_key.replace("_to_", " → ").replace("_", " ").title()
            routes.append({
                "route": route_label,
                "distance_km": Decimal(str(route_data.get("distance_km", 0))),
                "estimated_fare": Decimal(str(route_data.get("estimated_fare", 0))),
            })

        return {"service_type": service_type, "routes": routes}

    async def update_routes(
        self, service_type: str, routes: dict, admin_id: uuid.UUID, admin_name: str
    ) -> dict | None:
        obj = await self.config_repo.get_by_service_type(service_type)
        if not obj:
            return None

        config_data = dict(obj.config) if obj.config else {}
        old_routes = config_data.get("route_pricing", {})
        config_data["route_pricing"] = routes
        await self.config_repo.update_config(service_type, config_data)

        await self.log_repo.create({
            "admin_id": admin_id,
            "admin_name": admin_name,
            "category": "fare",
            "change_description": f"Updated {service_type} route pricing ({len(routes)} routes)",
            "before_value": f"{len(old_routes)} routes",
            "after_value": f"{len(routes)} routes",
        })

        return await self.get_routes(service_type)

    async def get_commission_view(self, service_type: str) -> dict | None:
        obj = await self.config_repo.get_by_service_type(service_type)
        if not obj:
            return None

        config_data = obj.config or {}
        platform = Decimal(str(config_data.get("platform_commission", 0.18)))

        commission = await self.commission_repo.get_active()
        if commission:
            platform = commission.platform_percent / 100
            driver_share = commission.driver_percent / 100
            fleet_share = commission.fleet_percent / 100
        else:
            driver_share = Decimal("0.62")
            fleet_share = Decimal("0.20")

        return {
            "service_type": service_type,
            "platform_commission": platform,
            "driver_share": driver_share,
            "fleet_share": fleet_share,
        }
